"""Signed RealNews session tokens, using only the standard library (AGENTS.md §13).

A token is rn1.<base64url JSON payload>.<base64url HMAC-SHA256>. The user ID inside is only ever taken from a
verified Google credential, and is trusted later only because the signature proves this server wrote it.
"""
import base64
import hashlib
import hmac
import json
import time

PREFIX = "rn1."
SESSION_SECONDS = 30 * 24 * 60 * 60
MIN_SECRET_LENGTH = 32


def now_ms() -> int:
    """Milliseconds, so signing back in right after signing out isn't caught by the same revocation."""
    return int(time.time() * 1000)


def sessions_enabled(secret: str) -> bool:
    """A missing or short secret turns sessions off, so a guessable key can never sign anything."""
    return len(secret) >= MIN_SECRET_LENGTH


def is_session_token(token: str) -> bool:
    return token.startswith(PREFIX)


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str, secret: str) -> str:
    return _encode(hmac.new(secret.encode(), f"{PREFIX}{payload}".encode(), hashlib.sha256).digest())


def issue_session_token(subject: str, name: str, secret: str) -> tuple[str, int]:
    expires_at = int(time.time()) + SESSION_SECONDS
    claims = {"sub": subject, "name": name, "exp": expires_at, "iat": now_ms()}
    payload = _encode(json.dumps(claims, separators=(",", ":")).encode())
    return f"{PREFIX}{payload}.{_sign(payload, secret)}", expires_at


def read_session_token(token: str, secret: str) -> dict:
    """Returns the claims, or raises ValueError if the token is forged, malformed or expired."""
    if not sessions_enabled(secret) or not is_session_token(token):
        raise ValueError("Sessions are not available")
    payload, separator, signature = token[len(PREFIX):].partition(".")
    if not separator or not hmac.compare_digest(signature, _sign(payload, secret)):
        raise ValueError("Bad signature")
    try:
        claims = json.loads(_decode(payload))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Bad payload") from exc
    if not isinstance(claims, dict) or not claims.get("sub") or not isinstance(claims.get("exp"), int):
        raise ValueError("Bad claims")
    if claims["exp"] <= time.time():
        raise ValueError("Expired")
    return claims
