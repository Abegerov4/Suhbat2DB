import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    decode_access_token,
    decrypt,
    encrypt,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("s3cret-password")
    assert hashed.startswith("$argon2")
    assert verify_password("s3cret-password", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("s3cret-password", None)


def test_jwt_roundtrip() -> None:
    user_id = uuid.uuid4()
    assert decode_access_token(create_access_token(user_id)) == user_id


def test_jwt_expired_is_rejected() -> None:
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(UTC) - timedelta(minutes=1)},
        get_settings().jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_jwt_with_other_secret_is_rejected() -> None:
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "attacker-secret-attacker-secret-32b",
        algorithm=ALGORITHM,
    )
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(token)


def test_connection_string_encryption() -> None:
    url = "postgresql://reader:p@ssw0rd@db:5432/demo"
    token = encrypt(url)
    assert b"p@ssw0rd" not in token
    assert decrypt(token) == url
