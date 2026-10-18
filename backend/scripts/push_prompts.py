"""Загрузка промптов из app/agent/prompts/*.md в Langfuse Prompt Management.

Новая версия создаётся, только если текст изменился (label production переезжает на неё).
История версий в Langfuse — материал для слайда «эволюция промпта».

    cd backend && uv run python -m scripts.push_prompts "что изменилось"
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from langfuse import Langfuse

from app.agent.prompts import LANGFUSE_PREFIX, PROMPT_NAMES, local_template

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    load_dotenv(ROOT / ".env")
    message = " ".join(sys.argv[1:]) or "update from repository"
    langfuse = Langfuse()
    for name in PROMPT_NAMES:
        text = local_template(name)
        full_name = LANGFUSE_PREFIX + name
        try:
            current = langfuse.get_prompt(full_name, label="production", cache_ttl_seconds=0)
            if current.prompt == text:
                print(f"{full_name}: без изменений (v{current.version})")
                continue
        except Exception:  # промпта ещё нет
            pass
        created = langfuse.create_prompt(
            name=full_name, prompt=text, labels=["production"], type="text", commit_message=message
        )
        print(f"{full_name}: загружена версия v{created.version}")
    langfuse.flush()


if __name__ == "__main__":
    main()
