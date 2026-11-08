from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query

from app.date_window import window_end, window_start
from app.db.repository import Repository
from app.deps import get_repo
from app.models import Chamber, Member, Position, Vote

router = APIRouter(tags=["members"])
EASTERN = ZoneInfo("America/New_York")


async def load_member(bioguide_id: str, repo: Repository) -> Member:
    data = await repo.get_member(bioguide_id.upper())
    if not data:
        raise HTTPException(status_code=404, detail=f"Member {bioguide_id} not found")
    return Member.model_validate(data)


async def member_votes(bioguide_id: str, from_: date | None, to: date | None, chamber: Chamber | None,
                       position: Position | None, page: int, page_size: int, repo: Repository) -> dict:
    await load_member(bioguide_id, repo)
    # Always stay inside the 4-year window.
    start = max(window_start(), datetime.combine(from_, time.min, EASTERN)) if from_ else window_start()
    end = min(window_end(), datetime.combine(to, time.max, EASTERN)) if to else window_end()
    if start > end:
        raise HTTPException(status_code=400, detail="'from' must be on or before 'to'")
    docs, total = await repo.member_votes(bioguide_id.upper(), start, end, chamber, position, page, page_size)
    items = [{**Vote.model_validate(d).model_dump(by_alias=True, mode="json"), "position": d["position"]}
             for d in docs]
    return {"items": items, "page": page, "pageSize": page_size, "total": total}


@router.get("/members/{bioguide_id}", summary="Member details")
async def get_member(bioguide_id: str, repo: Repository = Depends(get_repo)):
    return (await load_member(bioguide_id, repo)).model_dump(by_alias=True, mode="json")


@router.get("/members/{bioguide_id}/votes", summary="A member's votes, newest first, paginated and filterable")
async def get_member_votes(
    bioguide_id: str,
    chamber: Chamber | None = Query(None),
    from_: date | None = Query(None, alias="from", description="YYYY-MM-DD, inclusive"),
    to: date | None = Query(None, description="YYYY-MM-DD, inclusive"),
    position: Position | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    repo: Repository = Depends(get_repo),
):
    return await member_votes(bioguide_id, from_, to, chamber, position, page, page_size, repo)
