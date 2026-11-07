from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["policies"])


@router.get("/policies/{policy_id}", summary="Policy details and its votes")
async def get_policy(policy_id: str):
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/policies/{policy_id}/articles", summary="News articles about a policy")
async def get_policy_articles(policy_id: str):
    raise HTTPException(status_code=501, detail="Not implemented yet")
