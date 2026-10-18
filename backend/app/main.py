from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, datasources, health, messages, sessions
from app.bootstrap import bootstrap
from app.core.config import get_settings
from app.core.db import get_engine
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, install_request_logging
from app.services.datasources import wait_background
from app.services.target_db import target_pools


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()  # проверка конфигурации при старте
    configure_logging(json_logs=settings.app_env == "prod")
    await bootstrap(settings)
    yield
    await wait_background()
    await target_pools.close_all()
    await get_engine().dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Suhbat2DB API", version="0.1.0", lifespan=lifespan)
    install_error_handlers(app)
    install_request_logging(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )
    for module in (health, auth, datasources, sessions, messages):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
