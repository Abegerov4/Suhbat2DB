"""Симулированный пользователь: отвечает на уточняющий вопрос агента.

Пользователь знает, что он имел в виду (размеченная трактовка из ambiguous_ru или
эталонный SQL для Spider/BIRD), и выбирает подходящий вариант. Сопоставление варианта
с трактовкой делает LLM-судья (gpt-4.1, temperature 0, кэшируется); если ни
один вариант не подходит — пользователь отвечает своими словами (free_text), как
сделал бы человек. Выборка решений судьи проверяется вручную (см. EVALS.md).
"""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.llm import LLM

SYSTEM = """Ты играешь роль пользователя аналитической системы. Ты задал вопрос, а система \
переспросила, что ты имел в виду. Ты точно знаешь, что имел в виду (раздел «Задуманный \
смысл»). Для каждой неоднозначности выбери вариант, который совпадает с задуманным смыслом. \
Если ни один вариант не совпадает — option_id оставь пустым и в free_text коротко, \
по-русски, опиши задуманное своими словами. Не выбирай вариант «на всякий случай»."""


class Choice(BaseModel):
    ambiguity_id: str
    option_id: str | None = Field(default=None, description="id выбранного варианта или null")
    free_text: str | None = Field(default=None, description="свой ответ, если варианта нет")


class Choices(BaseModel):
    answers: list[Choice]


def render_request(request: dict[str, Any]) -> str:
    lines = [request.get("question", "")]
    for a in request["ambiguities"]:
        lines.append(f"\nНеоднозначность {a['id']} («{a['span']}», {a['type']}):")
        for o in a["options"]:
            desc = f" — {o['description']}" if o.get("description") else ""
            lines.append(f"  {o['id']}: {o['label']}{desc}")
    return "\n".join(lines)


async def answer_clarification(
    llm: LLM, question: str, intent: str, request: dict[str, Any]
) -> list[dict[str, Any]]:
    user = (
        f"Твой вопрос: {question}\n\nЗадуманный смысл:\n{intent}\n\n"
        f"Уточняющий вопрос системы:\n{render_request(request)}"
    )
    # узел ambiguity — сильная модель (gpt-4.1) с temperature 0: на gpt-4.1-mini судья путал
    # «финансовый» и «календарный» квартал (этап 1, ambiguous_ru-amb-020)
    result = await llm.structured("ambiguity", [SystemMessage(SYSTEM), HumanMessage(user)], Choices)
    valid = {a["id"]: {o["id"] for o in a["options"]} for a in request["ambiguities"]}
    answers: list[dict[str, Any]] = []
    for a in request["ambiguities"]:
        choice = next((c for c in result.answers if c.ambiguity_id == a["id"]), None)
        if choice and choice.option_id in valid[a["id"]]:
            answers.append({"ambiguity_id": a["id"], "option_id": choice.option_id})
        else:
            text = (choice.free_text if choice and choice.free_text else intent)[:500]
            answers.append({"ambiguity_id": a["id"], "free_text": text})
    return answers
