"""Прогон набора через конфигурацию → evals/reports/<дата>_<набор>_<конфигурация>_s<seed>.json

    cd backend && uv run python -m evals.run --suite spider_subset --config agent --seed 1
    cd backend && uv run python -m evals.run --suite ambiguous_ru --config agent_no_clarify

Ответы LLM кэшируются (evals/data/llm_cache.sqlite): повторный прогон бесплатный.
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from typing import Any, cast

from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient

from app.agent.factory import make_embedder
from app.agent.llm import LangChainLLM, NodeKey
from app.core.config import Settings, get_settings
from evals.cache import CachedLLM, LLMCache
from evals.config import EvalConfig, load_config
from evals.datasets import SUITES, load_suite, stratified
from evals.paths import DATA, REPORTS, ROOT, local_env_defaults
from evals.runner import System
from evals.runtime import Resources
from evals.summarize import summarize


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def eval_settings() -> Settings:
    """Промпты — из файлов репозитория (а не из Langfuse): прогон воспроизводим по коммиту."""
    return get_settings().model_copy(update={"prompts_from_langfuse": False})


async def run(
    suite: str,
    config: EvalConfig,
    *,
    seed: int,
    limit: int | None,
    concurrency: int,
    reindex: bool = False,
    langfuse: bool = True,
    report_name: str | None = None,
) -> dict[str, Any]:
    settings = eval_settings()
    if suite == "unsafe" and not config.explain:
        # без пояснения не проверить, выполнил ли агент инструкцию из данных
        config = EvalConfig(**{**config.as_dict(), "explain": True})
    cases = load_suite(suite)
    if limit:
        cases = stratified(cases, limit, seed=0)  # одна и та же подвыборка для всех seed

    cache = LLMCache(DATA / "llm_cache.sqlite")
    llm = CachedLLM(
        LangChainLLM(
            settings,
            cast(dict[NodeKey, str], config.models),
            cast(dict[NodeKey, float], config.temperatures),
            seed=seed,
        ),
        cache,
    )
    user_llm = CachedLLM(LangChainLLM(settings, seed=0), cache)
    client = AsyncQdrantClient(url=settings.qdrant_url)
    resources = Resources(store=_store(client, settings), reindex=reindex)
    run_id = f"{suite}:{config.name}:s{seed}:{datetime.now(UTC):%Y%m%d%H%M%S}"
    system = System(
        config=config,
        settings=settings,
        llm=llm,
        user_llm=user_llm,
        resources=resources,
        run_id=run_id,
        langfuse=langfuse and settings.langfuse_enabled,
    )

    semaphore = asyncio.Semaphore(concurrency)
    done = 0
    started = time.perf_counter()

    async def one(case: Any) -> dict[str, Any]:
        nonlocal done
        async with semaphore:
            result = await system.run(case)
        done += 1
        mark = "✓" if result.get("correct") else "✗"
        print(f"\r[{done}/{len(cases)}] {mark} {case.id:<28}", end="", file=sys.stderr, flush=True)
        return result

    try:
        results = await asyncio.gather(*(one(c) for c in cases))
    finally:
        await resources.close()
        await client.close()
    print(file=sys.stderr)

    report = {
        "meta": {
            "suite": suite,
            "config": config.as_dict(),
            "seed": seed,
            "limit": limit,
            "n": len(results),
            "git_sha": git_sha(),
            "run_id": run_id,
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "models": {
                node: llm.model_name(node) for node in ("guard", "ambiguity", "generate_sql")
            },
            "duration_s": round(time.perf_counter() - started, 1),
        },
        "summary": summarize(suite, results),
        "cases": sorted(results, key=lambda r: r["id"]),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    name = report_name or f"{datetime.now(UTC):%Y-%m-%d}_{suite}_{config.name}_s{seed}"
    (REPORTS / f"{name}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1, default=str) + "\n",
        encoding="utf-8",
    )
    return report


def _store(client: AsyncQdrantClient, settings: Settings) -> Any:
    from app.agent.retrieval.store import SchemaStore

    return SchemaStore(client, make_embedder(settings))


def main() -> None:
    load_dotenv(ROOT / ".env")
    local_env_defaults()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, choices=SUITES)
    parser.add_argument("--config", required=True)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--reindex", action="store_true", help="заново снять схему и индекс")
    parser.add_argument("--no-langfuse", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(
        run(
            args.suite,
            load_config(args.config),
            seed=args.seed,
            limit=args.limit,
            concurrency=args.concurrency,
            reindex=args.reindex,
            langfuse=not args.no_langfuse,
        )
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
