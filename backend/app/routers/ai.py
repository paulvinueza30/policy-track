"""DeepSeek summary endpoint. Owned by the AI teammate (AGENTS.md §6); not implemented here."""
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["ai"])


@router.post("/ai/summary", summary="DeepSeek summary for a policy")
async def ai_summary(body: dict):
    raise HTTPException(status_code=501, detail="Not implemented yet")
