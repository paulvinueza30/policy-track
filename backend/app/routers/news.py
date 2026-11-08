"""Home page news feed (AGENTS.md §4.4)."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from google.api_core.exceptions import GoogleAPIError

from app.config import settings
from app.db.repository import Repository
from app.deps import get_http, get_repo
from app.models import Article
from app.services.news import NewsError, fetch_feed

router = APIRouter(tags=["news"])
logger = logging.getLogger(__name__)

META_KEY = "newsFeed"
FEED_TTL = timedelta(hours=3)
EMPTY_FEED_TTL = timedelta(hours=1)
CACHE_WRITE_SECONDS = 5.0

_refresh_lock = asyncio.Lock()  # concurrent page loads share one refresh, to protect the daily quota


def _response(cached: dict) -> list[dict]:
    return [Article.model_validate(a).model_dump(by_alias=True, mode="json") for a in cached.get("articles", [])]


def _is_fresh(cached: dict, now: datetime) -> bool:
    fetched_at = cached.get("fetchedAt")
    ttl = FEED_TTL if cached.get("articles") else EMPTY_FEED_TTL
    return bool(fetched_at) and now - fetched_at < ttl


async def _save(repo: Repository, data: dict) -> None:
    try:
        await asyncio.wait_for(repo.set_meta(META_KEY, data), timeout=CACHE_WRITE_SECONDS)
    except (GoogleAPIError, TimeoutError) as e:
        logger.warning("Could not cache the news feed: %s", e)


@router.get("/news", summary="Latest news about Congress from vetted outlets (cached 3 hours)")
async def get_news(repo: Repository = Depends(get_repo), http: httpx.AsyncClient = Depends(get_http)):
    cached = await repo.get_meta(META_KEY)
    if _is_fresh(cached, datetime.now(timezone.utc)):
        return _response(cached)

    async with _refresh_lock:
        cached = await repo.get_meta(META_KEY)  # another request may have just refreshed it
        now = datetime.now(timezone.utc)
        if _is_fresh(cached, now):
            return _response(cached)
        try:
            articles = await fetch_feed(http, settings.news_api_key)
        except NewsError as e:
            if cached.get("articles"):
                return _response(cached)  # serve stale articles rather than nothing
            raise HTTPException(status_code=503, detail=f"News is unavailable right now: {e}")

        if not articles and cached.get("articles"):
            await _save(repo, {"fetchedAt": now - FEED_TTL + EMPTY_FEED_TTL})  # keep the old feed, retry in an hour
            return _response(cached)
        data = {"fetchedAt": now, "articles": [a.model_dump(by_alias=True) for a in articles]}
        await _save(repo, data)
        return _response(data)
