from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["ai"])


@router.post("/ai/summary", summary="DeepSeek summary for a policy")
async def ai_summary(body: dict):
    raise HTTPException(status_code=501, detail="Not implemented yet")
