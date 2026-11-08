from fastapi import APIRouter, Depends, HTTPException

from app.db.repository import Repository
from app.deps import get_repo
from app.models import Senator
from app.states import normalize_state

router = APIRouter(tags=["states"])


@router.get("/states/{state_code}/senators", summary="Senators for a state in the 4-year window")
async def get_state_senators(state_code: str, repo: Repository = Depends(get_repo)):
    state = normalize_state(state_code)
    if not state:
        raise HTTPException(status_code=400, detail=f"Unknown state code: {state_code}")
    senators = [Senator.model_validate(d) for d in await repo.senators_by_state(state)]
    # Current senators first, then former ones by most recent departure.
    senators.sort(key=lambda s: (s.in_office_to is not None, -(s.in_office_to.timestamp() if s.in_office_to else 0), s.name))
    return [s.model_dump(by_alias=True, mode="json") for s in senators]
