from typing import Annotated

import jwt
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.fake import FakeAgentRunner
from app.agent.runner import AgentRunner
from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models import User, UserRole

DbSession = Annotated[AsyncSession, Depends(get_db)]

bearer = HTTPBearer(auto_error=False, description="JWT из POST /api/auth/login")


def unauthorized(message: str = "Требуется вход в систему") -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, "unauthorized", message)


async def current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise unauthorized()
    try:
        user_id = decode_access_token(credentials.credentials)
    except (jwt.InvalidTokenError, ValueError) as e:
        raise unauthorized("Недействительный или просроченный токен") from e
    user = await db.get(User, user_id)
    if user is None:
        raise unauthorized("Пользователь не найден")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def admin_user(user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN:
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Действие доступно только admin")
    return user


AdminUser = Annotated[User, Depends(admin_user)]


_runner: AgentRunner = FakeAgentRunner()


def get_runner() -> AgentRunner:
    """LangGraphAgentRunner после create_agent(), иначе заглушка; в тестах — overrides."""
    return _runner


def set_runner(runner: AgentRunner) -> None:
    global _runner
    _runner = runner


Runner = Annotated[AgentRunner, Depends(get_runner)]
