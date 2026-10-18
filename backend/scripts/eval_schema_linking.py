"""Оценка schema linking на evals/datasets/schema_linking/demo.jsonl.

Сравниваются модели эмбеддингов, режимы поиска (dense / BM25 / hybrid) и число таблиц.
Метрики:
  full_recall  — доля вопросов, для которых найдены ВСЕ нужные таблицы (без этого SQL неверен);
  table_recall — доля найденных нужных таблиц (микро-среднее);
  precision    — доля нужных среди отобранных (насколько «зашумлён» контекст);
  avg_tables   — среднее число таблиц в промпте.

    cd backend && uv run python -m scripts.eval_schema_linking
"""

import asyncio
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient

from app.agent.retrieval.embeddings import OpenAIEmbedder
from app.agent.retrieval.linker import SchemaLinker
from app.agent.retrieval.store import SchemaStore, SearchMode
from app.schemas.schema_snapshot import SchemaSnapshot

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evals/datasets/schema_linking/demo.jsonl"
SNAPSHOT = ROOT / "backend/tests/validator/demo_schema.json"
REPORTS = ROOT / "evals/reports"

EMBEDDERS = ["text-embedding-3-small", "text-embedding-3-large"]
MODES: list[SearchMode] = ["dense", "sparse", "hybrid"]
TOP_TABLES = [3, 5, 7]


async def evaluate(
    store: SchemaStore, snapshot: SchemaSnapshot, cases: list[dict[str, Any]], mode: SearchMode,
    top: int,
) -> dict[str, Any]:  # fmt: skip
    linker = SchemaLinker(store, top_tables=top, candidates=40, mode=mode)
    full = found = gold_total = selected_total = 0
    misses = []
    for case in cases:
        linked = await linker.link(case["question"], snapshot)
        gold, got = set(case["gold_tables"]), set(linked.table_names)
        found += len(gold & got)
        gold_total += len(gold)
        selected_total += len(got)
        if gold <= got:
            full += 1
        else:
            misses.append({"id": case["id"], "missing": sorted(gold - got)})
    return {
        "full_recall": round(full / len(cases), 3),
        "table_recall": round(found / gold_total, 3),
        "precision": round(found / selected_total, 3),
        "avg_tables": round(selected_total / len(cases), 2),
        "misses": misses,
    }


async def main() -> None:
    load_dotenv(ROOT / ".env")
    cases = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines()]
    snapshot = SchemaSnapshot.model_validate_json(SNAPSHOT.read_text(encoding="utf-8"))
    snapshot.datasource_id = "eval-demo"
    client = AsyncQdrantClient(url=os.environ.get("QDRANT_EVAL_URL", "http://localhost:6333"))

    results = []
    for model in EMBEDDERS:
        store = SchemaStore(client, OpenAIEmbedder(model, os.environ["OPENAI_API_KEY"]))
        await store.index(snapshot)
        for mode in MODES:
            if mode == "sparse" and model != EMBEDDERS[0]:
                continue  # BM25 не зависит от модели эмбеддингов
            for top in TOP_TABLES:
                r = await evaluate(store, snapshot, cases, mode, top)
                label = "—" if mode == "sparse" else model
                results.append({"embedder": label, "mode": mode, "top_tables": top, **r})
                print(
                    f"{label:24} {mode:7} top={top}  full_recall={r['full_recall']:.3f}  "
                    f"table_recall={r['table_recall']:.3f}  precision={r['precision']:.3f}  "
                    f"avg_tables={r['avg_tables']}"
                )
        await store.delete(snapshot.datasource_id)

    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"{date.today()}_schema_linking.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nОтчёт: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
