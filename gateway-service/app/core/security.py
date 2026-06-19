from datetime import datetime, timezone, timedelta
from typing import Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_private_key: str | None = None
_public_key: str | None = None


def _load_keys() -> None:
    global _private_key, _public_key
    try:
        with open(settings.jwt_private_key_path) as f:
            _private_key = f.read()
        with open(settings.jwt_public_key_path) as f:
            _public_key = f.read()
    except FileNotFoundError:
        # HS256 fallback for development — RS256 in prod
        _private_key = settings.secret_key
        _public_key = settings.secret_key


def _algo() -> str:
    _ensure_loaded()
    return settings.jwt_algorithm if _private_key != settings.secret_key else "HS256"


def _ensure_loaded() -> None:
    if _private_key is None:
        _load_keys()


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    _ensure_loaded()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {
        **data,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(payload, _private_key, algorithm=_algo())


def decode_token(token: str) -> dict[str, Any]:
    _ensure_loaded()
    return jwt.decode(
        token,
        _public_key,
        algorithms=[_algo()],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
