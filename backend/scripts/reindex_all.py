"""Переиндексация всех источников данных (схема + примеры в Qdrant).

make index   # внутри контейнера backend
"""

import asyncio

from sqlalchemy import select

from app.agent.factory import create_agent
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.models import Datasource
from app.services.datasources import index_datasource


async def main() -> None:
    agent = await create_agent(get_settings())
    if agent is None:
        raise SystemExit("Агент не настроен (нет ключа LLM) — индекс не нужен")
    async with get_sessionmaker()() as db:
        ids = list(await db.scalars(select(Datasource.id)))
    for datasource_id in ids:
        await index_datasource(datasource_id)
        print(f"проиндексирован {datasource_id}")
    await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
