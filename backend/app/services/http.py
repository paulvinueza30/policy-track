"""Shared HTTP client settings for calls to outside services."""
import httpx

USER_AGENT = "policy-track/0.1 (Senate vote tracker; https://github.com/paulvinueza30/policy-track)"


def make_client(timeout: float = 30.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
        follow_redirects=True,
    )
