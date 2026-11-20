"""Password policy, hashing, JWT, CAPTCHA and OTP helpers (TS Ch.4 p.42-43; FRD UM-14..17)."""
import base64
import hashlib
import hmac
import json
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

PASSWORD_RULES = (
    (r".{8,}", "at least 8 characters"),
    (r"[A-Z]", "an upper-case letter"),
    (r"[a-z]", "a lower-case letter"),
    (r"[0-9]", "a digit"),
    (r"[^A-Za-z0-9]", "a special character"),
)


def password_policy_errors(password: str) -> list[str]:
    return [msg for pattern, msg in PASSWORD_RULES if not re.search(pattern, password or "")]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt(rounds=10)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_access_token(user_id: int, jti: str | None = None) -> tuple[str, str]:
    s = get_settings()
    jti = jti or uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "jti": jti, "iat": now, "exp": now + timedelta(minutes=s.access_token_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), jti


def decode_access_token(token: str) -> dict | None:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except JWTError:
        return None


# ---------------------------------------------------------------- CAPTCHA
# Stateless arithmetic CAPTCHA: the token carries an HMAC of the answer + expiry,
# so no server-side store is needed. Production would use an image CAPTCHA.
def _sign(data: bytes) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), data, hashlib.sha256).hexdigest()


def new_captcha() -> dict:
    a, b = secrets.randbelow(9) + 1, secrets.randbelow(9) + 1
    op = secrets.choice(["+", "×"])
    answer = a + b if op == "+" else a * b
    payload = {"h": _sign(f"{answer}".encode()), "exp": int(time.time()) + 300, "n": secrets.token_hex(4)}
    raw = json.dumps(payload).encode()
    token = base64.urlsafe_b64encode(raw).decode() + "." + _sign(raw)
    return {"captcha_token": token, "question": f"{a} {op} {b} = ?"}


def verify_captcha(token: str | None, answer: str | None) -> bool:
    if not get_settings().captcha_enabled:
        return True
    if not token or answer is None:
        return False
    try:
        raw_b64, sig = token.rsplit(".", 1)
        raw = base64.urlsafe_b64decode(raw_b64.encode())
        if not hmac.compare_digest(sig, _sign(raw)):
            return False
        payload = json.loads(raw)
        if payload["exp"] < time.time():
            return False
        return hmac.compare_digest(payload["h"], _sign(str(answer).strip().encode()))
    except Exception:  # noqa: BLE001 - any malformed token is simply invalid
        return False


# ---------------------------------------------------------------- OTP
def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    return hashlib.sha256(("otp:" + otp).encode()).hexdigest()
