"""Промпты агента: локальные файлы *.md — источник правды и fallback.

При PROMPTS_FROM_LANGFUSE=true версии берутся из Langfuse Prompt Management
(label production, имя suhbat2db-<name>) и привязываются к генерациям в трассах.
Загрузка в Langfuse: `uv run python -m scripts.push_prompts`.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.core.config import Settings

PromptName = Literal["guard", "ambiguity", "generate_sql", "explain", "baseline"]
PROMPT_NAMES: tuple[PromptName, ...] = (
    "guard",
    "ambiguity",
    "generate_sql",
    "explain",
    "baseline",
)
LANGFUSE_PREFIX = "suhbat2db-"
HERE = Path(__file__).resolve().parent
VARIABLE_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


@dataclass(frozen=True)
class Prompt:
    name: str
    template: str
    langfuse_prompt: Any | None = None  # TextPromptClient — для связи генерации с версией

    def compile(self, **variables: str) -> str:
        return VARIABLE_RE.sub(lambda m: variables.get(m.group(1), m.group(0)), self.template)

    def metadata(self) -> dict[str, Any]:
        return {"langfuse_prompt": self.langfuse_prompt} if self.langfuse_prompt else {}


def local_template(name: PromptName) -> str:
    return (HERE / f"{name}.md").read_text(encoding="utf-8").strip()


class PromptRegistry:
    def __init__(self, settings: Settings) -> None:
        self.use_langfuse = settings.prompts_from_langfuse and settings.langfuse_enabled
        self.local = {name: local_template(name) for name in PROMPT_NAMES}

    def get(self, name: PromptName) -> Prompt:
        if self.use_langfuse:
            from langfuse import get_client

            client = get_client().get_prompt(
                LANGFUSE_PREFIX + name,
                label="production",
                fallback=self.local[name],
                cache_ttl_seconds=300,
            )
            return Prompt(name, str(client.prompt), client)
        return Prompt(name, self.local[name])
