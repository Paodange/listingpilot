"""
Authentication utilities: JWT tokens + password hashing.
Uses hashlib + salt (no bcrypt dependency issues).
"""

import hashlib
import os
import secrets
import time

import jwt

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-to-a-random-string")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "72"))


def hash_password(password: str) -> str:
    """Hash password with random salt using SHA-256."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against stored hash."""
    try:
        salt, stored_hash = hashed.split("$", 1)
        h = hashlib.sha256((salt + plain).encode()).hexdigest()
        return secrets.compare_digest(h, stored_hash)
    except (ValueError, AttributeError):
        return False


def create_token(user_id: int, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": time.time() + TOKEN_EXPIRE_HOURS * 3600,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Returns payload dict or None if invalid/expired."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except (jwt.InvalidTokenError, jwt.DecodeError):
        return None
