from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.date_window import window_start
from app.db.repository import Repository
from app.deps import get_http, get_repo
from app.models import Article, Policy, Vote
from app.services.news import NewsError, search_articles
from app.services.vote_types import split_policy_id

router = APIRouter(tags=["policies"])
ARTICLE_TTL = timedelta(hours=24)


async def _load_policy(policy_id: str, repo: Repository) -> dict:
    try:
        split_policy_id(policy_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="policyId must look like 118-hr-2 or 119-pn-123")
    data = await repo.get_policy(policy_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return data


@router.get("/policies/{policy_id}", summary="Policy details and its votes")
async def get_policy(policy_id: str, repo: Repository = Depends(get_repo)):
    policy_id = policy_id.lower()
    data = await _load_policy(policy_id, repo)
    votes = [Vote.model_validate(v).model_dump(by_alias=True, mode="json") for v in await repo.policy_votes(policy_id)]
    return {**Policy.model_validate(data).model_dump(by_alias=True, mode="json"), "votes": votes}


def _sorted(articles: list[dict]) -> list[dict]:
    out = [Article.model_validate(a).model_dump(by_alias=True, mode="json") for a in articles]
    return sorted(out, key=lambda a: a.get("publishedAt") or "", reverse=True)


@router.get("/policies/{policy_id}/articles", summary="News articles about a policy (cached 24 hours)")
async def get_policy_articles(policy_id: str, repo: Repository = Depends(get_repo),
                              http: httpx.AsyncClient = Depends(get_http)):
    policy_id = policy_id.lower()
    data = await _load_policy(policy_id, repo)
    fetched_at = data.get("articlesFetchedAt")
    now = datetime.now(timezone.utc)
    if fetched_at and now - fetched_at < ARTICLE_TTL:
        return _sorted(await repo.get_articles(policy_id))

    try:
        articles = await search_articles(http, settings.news_api_key, Policy.model_validate(data),
                                         since=window_start())
    except NewsError as e:
        cached = await repo.get_articles(policy_id)
        if cached:  # serve stale articles rather than nothing
            return _sorted(cached)
        raise HTTPException(status_code=503, detail=f"News is unavailable right now: {e}")
    await repo.replace_articles(policy_id, articles, now)
    return _sorted([a.model_dump(by_alias=True) for a in articles])
