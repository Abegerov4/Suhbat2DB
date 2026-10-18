"""Пароли (argon2), JWT и шифрование строк подключения (Fernet)."""

import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from cryptography.fernet import Fernet
from pwdlib import PasswordHash

from app.core.config import get_settings

ALGORITHM = "HS256"

password_hash = PasswordHash.recommended()
# хэш-заглушка: проверка пароля для несуществующего email занимает то же время
DUMMY_HASH = password_hash.hash("timing-attack-protection")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    return password_hash.verify(password, hashed or DUMMY_HASH) and hashed is not None


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID:
    """Возвращает id пользователя; бросает jwt.InvalidTokenError или ValueError."""
    payload = jwt.decode(
        token,
        get_settings().jwt_secret.get_secret_value(),
        algorithms=[ALGORITHM],
        options={"require": ["sub", "exp"]},
    )
    return uuid.UUID(payload["sub"])


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().app_encryption_key.get_secret_value().encode())


def encrypt(value: str) -> bytes:
    return _fernet().encrypt(value.encode())


def decrypt(token: bytes) -> str:
    return _fernet().decrypt(token).decode()
