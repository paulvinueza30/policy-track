from fastapi import APIRouter

from app.services.ai import is_up

router = APIRouter(tags=["health"])


@router.get("/health", summary="Backend and DeepSeek status")
async def health():
    return {"status": "ok", "deepseek": "up" if await is_up() else "down"}
