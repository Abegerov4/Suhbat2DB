"""Smoke-тест агента с настоящим LLM через API (docs/roles/05_ai_agent.md §5.8).

Задаёт вопросы демо-БД, печатает ход работы агента; на уточнения отвечает первым вариантом.

    cd backend && uv run python -m scripts.smoke_agent                 # 10 вопросов
    cd backend && uv run python -m scripts.smoke_agent "Свой вопрос"   # один вопрос
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = [
    "Сколько всего заказов в базе?",
    "Топ-5 регионов по выручке за 2025 год",
    "Покажи продажи за прошлый квартал",
    "Какой способ оплаты самый популярный?",
    "Динамика выручки по месяцам в 2026 году",
    "Средний чек онлайн и офлайн",
    "Кто лучший менеджер?",
    "Сколько клиентов ни разу ничего не купили?",
    "Удали все отменённые заказы",
    "Напиши стихотворение про осень",
]


def parse(block: str) -> tuple[str, Any] | None:
    fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
    return (fields["event"], json.loads(fields["data"])) if "event" in fields else None


async def stream(
    client: httpx.AsyncClient, url: str, body: dict[str, Any]
) -> list[tuple[str, Any]]:
    events = []
    async with client.stream("POST", url, json=body, timeout=180) as response:
        response.raise_for_status()
        buffer = ""
        async for text in response.aiter_text():
            buffer += text
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                if (event := parse(block)) is not None:
                    events.append(event)
    return events


def show(events: list[tuple[str, Any]]) -> None:
    answer = "".join(d["text"] for t, d in events if t == "answer")
    for kind, data in events:
        if kind == "step" and data["status"] == "finished" and data.get("detail"):
            print(f"   · {data['node']}: {data['detail'][:110]}")
        elif kind == "sql":
            print(f"   SQL (попытка {data['attempt']}): " + " ".join(data["sql"].split())[:220])
        elif kind == "validation" and not data["passed"]:
            print(f"   ✗ уровень {data['level']}: {data['message'][:120]}")
        elif kind == "result":
            print(f"   ✓ строк: {data['row_count']}; первые: {data['rows'][:3]}")
        elif kind == "chart":
            print(f"   график: {data['type']} ({data['x']} → {data['y']})")
        elif kind == "error":
            print(f"   ⛔ {data['code']}: {data['message']}")
        elif kind == "clarification":
            for a in data["ambiguities"]:
                print(
                    f"   ? {a['span']} ({a['type']}): "
                    + " | ".join(o["label"] for o in a["options"])
                )
    if answer:
        print(f"   💬 {answer}")
    done = next((d for t, d in events if t == "done"), {})
    if done.get("trace_id"):
        print(f"   trace: {done['trace_id']}")


async def main() -> None:
    load_dotenv(ROOT / ".env")
    api = f"http://localhost:{os.environ.get('BACKEND_PORT', '8000')}/api"
    questions = sys.argv[1:] or QUESTIONS
    async with httpx.AsyncClient(base_url=api) as client:
        token = (
            await client.post(
                "/auth/login",
                json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]},
            )
        ).json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        datasource = (await client.get("/datasources")).json()[0]
        for question in questions:
            session = (
                await client.post("/sessions", json={"datasource_id": datasource["id"]})
            ).json()
            print(f"\n▶ {question}")
            events = await stream(
                client, f"/sessions/{session['id']}/messages", {"content": question}
            )
            show(events)
            clarification = next((d for t, d in events if t == "clarification"), None)
            if clarification:
                answers = [
                    {"ambiguity_id": a["id"], "option_id": a["options"][0]["id"]}
                    for a in clarification["ambiguities"]
                ]
                print(
                    "   ↳ отвечаю: "
                    + ", ".join(a["options"][0]["label"] for a in clarification["ambiguities"])
                )
                show(
                    await stream(client, f"/sessions/{session['id']}/clarify", {"answers": answers})
                )


if __name__ == "__main__":
    asyncio.run(main())
