"""FastAPI app entry point. Run: uvicorn app.main:app --reload"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import ai, health, policies, senators, states, votes

app = FastAPI(title="Senate Vote Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


def error_response(status: int, code: str, message: str) -> JSONResponse:
    """Shared error shape: { "error": { "code", "message" } } (AGENTS.md §7)."""
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return error_response(exc.status_code, f"http_{exc.status_code}", str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return error_response(422, "validation_error", str(exc.errors()))


for router in (health.router, states.router, senators.router, votes.router, policies.router, ai.router):
    app.include_router(router, prefix="/api")
