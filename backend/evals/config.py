"""Конфигурации прогонов: evals/configs/<name>.yaml.

Конфигурация описывает систему целиком: baseline или агент, включённые узлы, уровни
валидатора, модель и temperature для узлов. Эксперимент = сравнение двух конфигураций
на одном наборе с одними и теми же seed'ами.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

import yaml

from evals.paths import CONFIGS

NODES = ("guard", "ambiguity", "generate_sql", "explain")


@dataclass(frozen=True)
class EvalConfig:
    name: str
    description: str = ""
    system: Literal["agent", "baseline"] = "agent"
    clarify: bool = True
    schema_linking: bool = True
    semantic_checks: bool = True  # уровни 3 (схема) и 4 (EXPLAIN) валидатора
    explain: bool = False  # пояснение не влияет на EX; включается для набора unsafe
    max_attempts: int = 3
    models: dict[str, str] = field(default_factory=dict)  # узел → модель
    temperatures: dict[str, float] = field(default_factory=dict)  # узел → temperature

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def load_config(name: str) -> EvalConfig:
    path = CONFIGS / f"{name}.yaml"
    if not path.exists():
        known = ", ".join(sorted(p.stem for p in CONFIGS.glob("*.yaml")))
        raise SystemExit(f"Нет конфигурации {name!r}. Есть: {known}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key in ("models", "temperatures"):
        unknown = set(data.get(key, {})) - set(NODES)
        if unknown:
            raise SystemExit(f"{path.name}: неизвестные узлы в {key}: {sorted(unknown)}")
    return EvalConfig(name=name, **data)
