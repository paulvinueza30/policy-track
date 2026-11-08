"""Authenticated personal feeds. Google subject is the owner; never accept a user ID from clients."""
import asyncio
import re
import time
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from pydantic import Field

from app.config import settings
from app.db.repository import Repository
from app.deps import get_repo
from app.models import CamelModel, Member, Vote
from app.date_window import window_start, window_end

router = APIRouter(tags=["account"])

@lru_cache(maxsize=128)
def verified_claims(token: str, audience: str) -> dict:
    return id_token.verify_oauth2_token(token, Request(), audience)



async def identity(authorization: str = Header(default="")) -> dict:
    if not settings.google_client_id:
        raise HTTPException(503, "Google sign-in has not been configured yet")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in to continue")
    token = authorization[7:]
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
    following: list[str] = Field(default_factory=list, max_length=20)


@router.get("/account")
async def account(user: dict = Depends(identity), repo: Repository = Depends(get_repo)) -> dict:
    return {**user, "preferences": await repo.get_preferences(user["id"])}


@router.put("/account/preferences")
async def save_preferences(body: Preferences, user: dict = Depends(identity), repo: Repository = Depends(get_repo)) -> dict:
    from app.states import STATE_CODES
    if (body.state is None) != (body.district is None) or (body.state and body.state not in STATE_CODES):
        raise HTTPException(422, "Select a state and district together")
    if body.state:
        delegation = [Member.model_validate(m) for m in await repo.members_by_state(body.state)]
        if not any(m.for_chamber("house") and m.for_chamber("house").district == body.district for m in delegation):
            raise HTTPException(422, "That district is not available in the member data")
    body.following = list(dict.fromkeys(value.upper() for value in body.following))
    for member in body.following:
        if not re.fullmatch(r"[A-Z]\d{6}", member) or not await repo.get_member(member):
            raise HTTPException(422, "A followed member could not be found")
    for policy_id in body.reactions:
        if not re.fullmatch(r"\d+-(?:hr|s|hres|sres|hjres|sjres|hconres|sconres|pn)-\d+", policy_id):
            raise HTTPException(422, "Invalid policy reaction")
    preferences = body.model_dump(by_alias=True)
    await repo.save_preferences(user["id"], preferences)
    return preferences


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
