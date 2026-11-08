from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import settings
from app.date_window import window_start
from app.db.repository import Repository
from app.deps import get_http, get_repo
from app.models import Article, MemberVote, Policy, PolicySummary, Vote
from app.services.ai.prompts import (PolicyContext, StateVote, build_sources, newest_per_chamber, record_key_points,
                                     record_summary_text, state_vote_point)
from app.services.news import NewsError, belongs_on_policy_page, search_articles
from app.services.vote_types import split_policy_id
from app.states import normalize_state

router = APIRouter(tags=["policies"])
ARTICLE_TTL = timedelta(hours=24)
EMPTY_ARTICLE_TTL = timedelta(hours=1)


async def _load_policy(policy_id: str, repo: Repository) -> dict:
    try:
        split_policy_id(policy_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="policyId must look like 118-hr-2 or 119-pn-123")
    data = await repo.get_policy(policy_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return data


def _state(code: str | None) -> str | None:
    if not code:
        return None
    state = normalize_state(code)
    if not state:
        raise HTTPException(status_code=400, detail="stateCode must be one of the 50 state codes")
    return state


async def _votes(policy_id: str, repo: Repository) -> list[Vote]:
    return [Vote.model_validate(v) for v in await repo.policy_votes(policy_id)]


async def _state_votes(state: str | None, votes: list[Vote], repo: Repository) -> list[StateVote]:
    """The state's members on the newest roll call in each chamber."""
    if not state:
        return []
    out = []
    for vote in newest_per_chamber(votes):
        doc = await repo.get_vote(vote.vote_id) or {}
        members = [MemberVote.model_validate(m) for m in doc.get("members", []) if m.get("state") == state]
        if members:
            out.append(StateVote(vote=vote, members=members))
    return out


@router.get("/policies/{policy_id}", summary="Policy details and its votes")
async def get_policy(policy_id: str, repo: Repository = Depends(get_repo)):
    policy_id = policy_id.lower()
    data = await _load_policy(policy_id, repo)
    votes = [Vote.model_validate(v).model_dump(by_alias=True, mode="json") for v in await repo.policy_votes(policy_id)]
    return {**Policy.model_validate(data).model_dump(by_alias=True, mode="json"), "votes": votes}


@router.get("/policies/{policy_id}/summary", summary="A policy's summary from the official record (no AI)")
async def get_policy_summary(policy_id: str, state_code: str | None = Query(default=None, alias="stateCode"),
                             repo: Repository = Depends(get_repo)):
    policy_id = policy_id.lower()
    state = _state(state_code)
    policy = Policy.model_validate(await _load_policy(policy_id, repo))
    votes = await _votes(policy_id, repo)
    points = record_key_points(policy, votes)
    points += [state_vote_point(state, s) for s in await _state_votes(state, votes, repo)]
    summary = PolicySummary(policy_id=policy_id, summary=policy.crs_summary or record_summary_text(policy),
                            key_points=points, sources=build_sources(PolicyContext(policy=policy, votes=votes)))
    return summary.model_dump(by_alias=True, mode="json")


def _sorted(articles: list[dict], policy: Policy) -> list[dict]:
    """Filtered here, on the way out, so articles cached before a rule changed are covered too."""
    kept = [a for a in map(Article.model_validate, articles) if belongs_on_policy_page(a, policy)]
    out = [a.model_dump(by_alias=True, mode="json") for a in kept]
    return sorted(out, key=lambda a: a.get("publishedAt") or "", reverse=True)


@router.get("/policies/{policy_id}/articles", summary="News articles about a policy (cached 24 hours; empty results 1 hour)")
async def get_policy_articles(policy_id: str, repo: Repository = Depends(get_repo),
                              http: httpx.AsyncClient = Depends(get_http)):
    policy_id = policy_id.lower()
    data = await _load_policy(policy_id, repo)
    policy = Policy.model_validate(data)
    fetched_at = data.get("articlesFetchedAt")
    now = datetime.now(timezone.utc)
    cached = await repo.get_articles(policy_id) if fetched_at else []
    if fetched_at and now - fetched_at < (ARTICLE_TTL if cached else EMPTY_ARTICLE_TTL):
        return _sorted(cached, policy)

    try:
        articles = await search_articles(http, settings.news_api_key, policy, since=window_start())
    except NewsError as e:  # never recorded as a fetch, so errors and rate limits are retried on the next load
        if cached:  # serve stale articles rather than nothing
            return _sorted(cached, policy)
        raise HTTPException(status_code=503, detail=f"News is unavailable right now: {e}")
    if not articles and cached:  # a blank response must not erase articles we already have
        await repo.touch_articles(policy_id, now - ARTICLE_TTL + EMPTY_ARTICLE_TTL)  # keep them, retry in an hour
        return _sorted(cached, policy)
    await repo.replace_articles(policy_id, articles, now)
    return _sorted([a.model_dump(by_alias=True) for a in articles], policy)
