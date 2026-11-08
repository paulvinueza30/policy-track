"""Deprecated aliases so the current frontend keeps working. Delete after it moves to /members (AGENTS.md §7)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.repository import Repository
from app.deps import get_repo
from app.models import Position
from app.routers.members import load_member, member_votes

router = APIRouter(tags=["senators (deprecated)"])


@router.get("/senators/{bioguide_id}", summary="Deprecated: use /members/{bioguide_id}", deprecated=True)
async def get_senator(bioguide_id: str, repo: Repository = Depends(get_repo)):
    senator = (await load_member(bioguide_id, repo)).for_chamber("senate")
    if not senator:
        raise HTTPException(status_code=404, detail=f"Senator {bioguide_id} not found")
    return senator.model_dump(by_alias=True, mode="json")


@router.get("/senators/{bioguide_id}/votes", summary="Deprecated: use /members/{bioguide_id}/votes", deprecated=True)
async def get_senator_votes(
    bioguide_id: str,
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None),
    position: Position | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    repo: Repository = Depends(get_repo),
):
    return await member_votes(bioguide_id, from_, to, "senate", position, page, page_size, repo)
