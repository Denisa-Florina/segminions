"""Password hashing, access tokens (JWT) and the authentication guard for routes."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from flask import current_app, g, request

from app.core.errors import AuthenticationError

_JWT_ALGORITHM = "HS256"


# --- Passwords -------------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def is_legacy_hash(stored_hash: str) -> bool:
    """True for the unsalted SHA-256 hashes created before the move to bcrypt."""
    return not stored_hash.startswith("$2")


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    if is_legacy_hash(stored_hash):
        legacy = hashlib.sha256(password.encode()).hexdigest()
        return hmac.compare_digest(legacy, stored_hash)
    return bcrypt.checkpw(password.encode(), stored_hash.encode())


# --- Access tokens ---------------------------------------------------------

def create_access_token(doctor_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": doctor_id,
        "iat": now,
        "exp": now + timedelta(minutes=current_app.config["ACCESS_TOKEN_TTL_MINUTES"]),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[_JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Session expired, please log in again") from None
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid authentication token") from None
    return payload["sub"]


# --- Request guard ---------------------------------------------------------

def require_authentication() -> None:
    """Blueprint `before_request` hook: rejects requests without a valid Bearer token."""
    if request.method == "OPTIONS":  # CORS preflight carries no credentials
        return
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("Not authenticated")
    g.doctor_id = decode_access_token(token)


def current_doctor_id() -> str:
    """Id of the authenticated doctor; only valid behind `require_authentication`."""
    return g.doctor_id
