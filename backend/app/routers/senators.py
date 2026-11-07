from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["senators"])


@router.get("/senators/{bioguide_id}", summary="Senator details")
async def get_senator(bioguide_id: str):
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/senators/{bioguide_id}/votes", summary="A senator's votes, paginated and filterable")
async def get_senator_votes(bioguide_id: str, from_: str | None = Query(None, alias="from"), to: str | None = None, position: str | None = None, page: int = 1):
    raise HTTPException(status_code=501, detail="Not implemented yet")
