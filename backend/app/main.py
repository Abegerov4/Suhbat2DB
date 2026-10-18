from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_settings()  # проверка конфигурации при старте
    yield


app = FastAPI(title="Suhbat2DB API", version="0.1.0", lifespan=lifespan)
app.include_router(health.router, prefix="/api")
