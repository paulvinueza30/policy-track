from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.repository import Repository
from app.deps import get_repo
from app.models import Chamber, Member
from app.states import normalize_state

router = APIRouter(tags=["states"])


def _sort_key(m: Member) -> tuple:
    """Senators first, then by district; current members first, then most recent departure."""
    return (m.chamber != "senate", m.district or 0, m.in_office_to is not None,
            -(m.in_office_to.timestamp() if m.in_office_to else 0), m.name)


async def state_members(state_code: str, chamber: Chamber | None, repo: Repository) -> list[dict]:
    state = normalize_state(state_code)
    if not state:
        raise HTTPException(status_code=400, detail=f"Unknown state code: {state_code}")
    members = [Member.model_validate(d) for d in await repo.members_by_state(state)]
    if chamber:  # describe each person's service in the requested chamber
        members = [m for m in (member.for_chamber(chamber) for member in members) if m]
    members.sort(key=_sort_key)
    return [m.model_dump(by_alias=True, mode="json") for m in members]


@router.get("/states/{state_code}/members", summary="A state's members of Congress in the 4-year window")
async def get_state_members(state_code: str, chamber: Chamber | None = Query(None),
                            repo: Repository = Depends(get_repo)):
    return await state_members(state_code, chamber, repo)


@router.get("/states/{state_code}/senators", summary="Deprecated: use /states/{state_code}/members?chamber=senate",
            deprecated=True)
async def get_state_senators(state_code: str, repo: Repository = Depends(get_repo)):
    return await state_members(state_code, "senate", repo)
