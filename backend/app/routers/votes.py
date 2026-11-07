from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["votes"])


@router.get("/votes/{vote_id}", summary="One roll-call vote with every senator's position")
async def get_vote(vote_id: str):
    raise HTTPException(status_code=501, detail="Not implemented yet")
