from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Backend and DeepSeek status")
async def health():
    # TODO: ping the DeepSeek server and report "up" or "down".
    return {"status": "ok", "deepseek": "unknown"}
