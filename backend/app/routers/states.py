from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["states"])


@router.get("/states/{state_code}/senators", summary="Senators for a state in the 4-year window")
async def get_state_senators(state_code: str):
    raise HTTPException(status_code=501, detail="Not implemented yet")
