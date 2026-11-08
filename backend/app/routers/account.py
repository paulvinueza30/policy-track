"""Authenticated personal feeds. Google subject is the owner; never accept a user ID from clients."""
import asyncio
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from google.api_core.exceptions import GoogleAPIError
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from pydantic import Field

from app.config import settings
from app.db.repository import FollowLimitReached, Repository
from app.deps import get_http, get_repo
from app.models import Article, CamelModel, Member, Vote
from app.date_window import window_start, window_end
from app.services.news import NewsError, headline_key, search_member_articles
from app.services.sessions import is_session_token, issue_session_token, now_ms, read_session_token, sessions_enabled

router = APIRouter(tags=["account"])
logger = logging.getLogger(__name__)

MAX_FOLLOWING = 20
MEMBER_NEWS_TTL = timedelta(hours=12)
EMPTY_MEMBER_NEWS_TTL = timedelta(hours=1)
MAX_MEMBER_FETCHES = 5
MAX_NEWS_ITEMS = 24
CACHE_WRITE_SECONDS = 5.0
SESSION_CHECK_SECONDS = 5.0
FOLLOW_RETRY_MESSAGE = "Your follows could not be updated. Please try again."

_member_news_lock = asyncio.Lock()  # concurrent page loads share the work, to protect the daily quota

@lru_cache(maxsize=128)
def verified_claims(token: str, audience: str) -> dict:
    return id_token.verify_oauth2_token(token, Request(), audience)



async def identity(authorization: str = Header(default=""), repo: Repository = Depends(get_repo)) -> dict:
    token = authorization[7:] if authorization.startswith("Bearer ") else ""
    if is_session_token(token):
        if len(token) > 8192:
            raise HTTPException(401, "Invalid sign-in credential")
        try:
            claims = read_session_token(token, settings.session_secret)
        except ValueError as exc:
            raise HTTPException(401, "Your sign-in expired or is invalid. Please sign in again.") from exc
        try:  # if this can't be checked the session is refused, so a revoked token can't slip through
            valid_after = await asyncio.wait_for(repo.sessions_valid_after(claims["sub"]), timeout=SESSION_CHECK_SECONDS)
        except (GoogleAPIError, TimeoutError) as exc:
            raise HTTPException(503, "Your sign-in could not be checked. Please try again.") from exc
        if valid_after and claims.get("iat", 0) <= valid_after:
            raise HTTPException(401, "Your sign-in expired or is invalid. Please sign in again.")
        return {"id": claims["sub"], "name": claims.get("name", "Citizen"), "expiresAt": claims["exp"]}
    return await google_identity(token)


async def google_identity(token: str) -> dict:
    if not settings.google_client_id:
        raise HTTPException(503, "Google sign-in has not been configured yet")
    if not token:
        raise HTTPException(401, "Sign in to continue")
    if len(token) > 8192:
        raise HTTPException(401, "Invalid sign-in credential")
    try:
        claims = await asyncio.to_thread(verified_claims, token, settings.google_client_id)
        if claims.get("exp", 0) <= time.time() or not claims.get("sub") or claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            raise ValueError("Invalid issuer")
        return {"id": claims["sub"], "name": claims.get("name", "Citizen"), "expiresAt": claims["exp"]}
    except ValueError as exc:
        raise HTTPException(401, "Your sign-in expired or is invalid. Please sign in again.") from exc
    except Exception as exc:
        raise HTTPException(503, "Google sign-in verification is unavailable") from exc


class Preferences(CamelModel):
    state: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    district: int | None = Field(default=None, ge=0, le=99)
    reactions: dict[str, Literal["like", "dislike"]] = Field(default_factory=dict, max_length=200)
    following: list[str] | None = Field(default=None, max_length=MAX_FOLLOWING)  # omitted = leave follows unchanged


class SessionRequest(CamelModel):
    credential: str = Field(min_length=1, max_length=8192)


@router.post("/account/session", summary="Exchange a Google credential for a RealNews session")
async def create_session(body: SessionRequest) -> dict:
    """Only a Google credential works here, so a session can't be renewed forever without signing in again."""
    if is_session_token(body.credential):
        raise HTTPException(401, "Invalid sign-in credential")
    user = await google_identity(body.credential)
    if not sessions_enabled(settings.session_secret):
        return {"token": body.credential, "expiresAt": user["expiresAt"], "name": user["name"]}
    token, expires_at = issue_session_token(user["id"], user["name"], settings.session_secret)
    return {"token": token, "expiresAt": expires_at, "name": user["name"]}


async def _existing_member_id(bioguide_id: str, repo: Repository) -> str:
    member_id = bioguide_id.upper()
    if not re.fullmatch(r"[A-Z]\d{6}", member_id) or not await repo.get_member(member_id):
        raise HTTPException(422, "A followed member could not be found")
    return member_id


@router.get("/account")
async def account(user: dict = Depends(identity), repo: Repository = Depends(get_repo)) -> dict:
    return {**user, "preferences": await repo.get_preferences(user["id"])}


@router.post("/account/sign-out", summary="Sign out and invalidate all of this user's RealNews sessions")
async def sign_out(user: dict = Depends(identity), repo: Repository = Depends(get_repo)) -> dict:
    await repo.revoke_sessions(user["id"], now_ms())
    return {"signedOut": True}


@router.delete("/account", summary="Delete the signed-in user's account data and sessions")
async def delete_account(user: dict = Depends(identity), repo: Repository = Depends(get_repo)) -> dict:
    await repo.delete_account(user["id"], now_ms())
    return {"deleted": True}


@router.put("/account/following/{bioguide_id}", summary="Follow a member")
async def follow(bioguide_id: str, user: dict = Depends(identity), repo: Repository = Depends(get_repo)) -> dict:
    member_id = await _existing_member_id(bioguide_id, repo)
    try:
        return {"following": await repo.add_following(user["id"], member_id, MAX_FOLLOWING)}
    except FollowLimitReached as exc:
        raise HTTPException(422, f"You can follow up to {MAX_FOLLOWING} members") from exc
    except (ValueError, GoogleAPIError) as exc:  # the transaction ran out of retries
        raise HTTPException(503, FOLLOW_RETRY_MESSAGE) from exc


@router.delete("/account/following/{bioguide_id}", summary="Stop following a member")
async def unfollow(bioguide_id: str, user: dict = Depends(identity), repo: Repository = Depends(get_repo)) -> dict:
    member_id = bioguide_id.upper()
    if not re.fullmatch(r"[A-Z]\d{6}", member_id):  # no lookup, so someone who has left the data can be unfollowed
        raise HTTPException(422, "A followed member could not be found")
    try:
        return {"following": await repo.remove_following(user["id"], member_id)}
    except (ValueError, GoogleAPIError) as exc:
        raise HTTPException(503, FOLLOW_RETRY_MESSAGE) from exc


def _member_news_is_fresh(doc: dict | None, now: datetime) -> bool:
    if not doc or not doc.get("fetchedAt"):
        return False
    return now - doc["fetchedAt"] < (MEMBER_NEWS_TTL if doc.get("articles") else EMPTY_MEMBER_NEWS_TTL)


async def _save_member_news(repo: Repository, member_id: str, data: dict) -> None:
    try:
        await asyncio.wait_for(repo.save_member_news(member_id, data), timeout=CACHE_WRITE_SECONDS)
    except (GoogleAPIError, TimeoutError) as exc:
        logger.warning("Could not cache news for %s: %s", member_id, exc)


async def _refresh_member_news(member_ids: list[str], cache: dict[str, dict], repo: Repository,
                               http: httpx.AsyncClient) -> bool:
    """Updates cache in place. False if GNews failed: nothing is cached, and the page shouldn't keep asking."""
    now = datetime.now(timezone.utc)
    for member_id in member_ids:
        record = await repo.get_member(member_id)
        if not record:
            cache[member_id] = {"fetchedAt": now, "articles": []}
            continue
        try:
            found = await search_member_articles(http, settings.news_api_key, Member.model_validate(record))
        except NewsError as exc:
            logger.warning("Member news is unavailable: %s", exc)
            return False
        previous = (cache.get(member_id) or {}).get("articles", [])
        if not found and previous:  # a blank response must not erase articles we already have
            data = {"fetchedAt": now - MEMBER_NEWS_TTL + EMPTY_MEMBER_NEWS_TTL, "articles": previous}
        else:
            data = {"fetchedAt": now, "articles": [a.model_dump(by_alias=True) for a in found]}
        cache[member_id] = data
        await _save_member_news(repo, member_id, data)
    return True


def _combined_news(following: list[str], cache: dict[str, dict]) -> list[dict]:
    by_url: dict[str, dict] = {}
    for member_id in following:
        for stored in (cache.get(member_id) or {}).get("articles", []):
            article = Article.model_validate(stored).model_dump(by_alias=True, mode="json", exclude={"policy_id"})
            by_url.setdefault(article["url"], {**article, "memberIds": []})["memberIds"].append(member_id)
    by_headline: dict[str, dict] = {}  # newest first, so the newest copy of a wire story is the one kept
    for item in sorted(by_url.values(), key=lambda a: a.get("publishedAt") or "", reverse=True):
        kept = by_headline.setdefault(headline_key(item["title"], item.get("source") or "") or item["url"], item)
        if kept is not item:
            kept["memberIds"] += [m for m in item["memberIds"] if m not in kept["memberIds"]]
    return list(by_headline.values())[:MAX_NEWS_ITEMS]


@router.get("/account/news", summary="News about the members this user follows")
async def account_news(user: dict = Depends(identity), repo: Repository = Depends(get_repo),
                       http: httpx.AsyncClient = Depends(get_http)) -> dict:
    following = (await repo.get_preferences(user["id"])).get("following", [])
    if not following:
        return {"items": [], "pending": False}
    cache = await repo.get_member_news(following)
    if all(_member_news_is_fresh(cache.get(m), datetime.now(timezone.utc)) for m in following):
        return {"items": _combined_news(following, cache), "pending": False}

    async with _member_news_lock:
        cache = await repo.get_member_news(following)  # another request may have just refreshed some
        now = datetime.now(timezone.utc)
        stale = [m for m in following if not _member_news_is_fresh(cache.get(m), now)]
        succeeded = await _refresh_member_news(stale[:MAX_MEMBER_FETCHES], cache, repo, http)
    return {"items": _combined_news(following, cache), "pending": succeeded and len(stale) > MAX_MEMBER_FETCHES}


@router.put("/account/preferences")
async def save_preferences(body: Preferences, user: dict = Depends(identity), repo: Repository = Depends(get_repo)) -> dict:
    from app.states import STATE_CODES
    if (body.state is None) != (body.district is None) or (body.state and body.state not in STATE_CODES):
        raise HTTPException(422, "Select a state and district together")
    if body.state:
        delegation = [Member.model_validate(m) for m in await repo.members_by_state(body.state)]
        if not any(m.for_chamber("house") and m.for_chamber("house").district == body.district for m in delegation):
            raise HTTPException(422, "That district is not available in the member data")
    if body.following is not None:
        body.following = list(dict.fromkeys(value.upper() for value in body.following))
    for member in body.following or []:
        if not re.fullmatch(r"[A-Z]\d{6}", member) or not await repo.get_member(member):
            raise HTTPException(422, "A followed member could not be found")
    for policy_id in body.reactions:
        if not re.fullmatch(r"\d+-(?:hr|s|hres|sres|hjres|sjres|hconres|sconres|pn)-\d+", policy_id):
            raise HTTPException(422, "Invalid policy reaction")
    preferences = body.model_dump(by_alias=True)
    if body.following is None:
        del preferences["following"]
    await repo.save_preferences(user["id"], preferences)
    return await repo.get_preferences(user["id"]) if body.following is None else preferences


@router.get("/account/feed")
async def feed(scope: Literal["local", "national", "following"] = "local",
               page: int = Query(1, ge=1, le=20), page_size: int = Query(12, alias="pageSize", ge=1, le=25),
               user: dict = Depends(identity), repo: Repository = Depends(get_repo)) -> dict:
    prefs = await repo.get_preferences(user["id"])
    member_ids = prefs.get("following", [])
    if scope == "local":
        if not prefs.get("state"):
            return {"items": [], "page": page, "hasMore": False, "needsDistrict": True}
        delegation = [Member.model_validate(m) for m in await repo.members_by_state(prefs["state"])]
        member_ids = [m.bioguide_id for m in delegation if m.in_office_to is None and
                      (m.chamber == "senate" or m.district == prefs.get("district"))]
    count = page * page_size + 1
    records = await repo.feed_votes(None if scope == "national" else member_ids, window_start(), window_end(), count)
    items = [Vote.model_validate(v).model_dump(by_alias=True, mode="json") for v in records]
    return {"items": items[(page - 1) * page_size:page * page_size], "page": page, "hasMore": len(items) > page * page_size}
