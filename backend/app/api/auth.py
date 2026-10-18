from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User, UserRole
from app.schemas.api import Credentials, Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: Credentials, db: DbSession) -> UserOut:
    """Регистрация аналитика. Администратор создаётся из env при старте."""
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        role=UserRole.ANALYST,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as e:
        raise AppError(
            status.HTTP_409_CONFLICT, "email_taken", "Пользователь с таким email уже есть"
        ) from e
    return UserOut.model_validate(user)


@router.post("/login")
async def login(body: Credentials, db: DbSession) -> Token:
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if not verify_password(body.password, user.password_hash if user else None) or user is None:
        raise AppError(
            status.HTTP_401_UNAUTHORIZED, "invalid_credentials", "Неверный email или пароль"
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/me")
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
