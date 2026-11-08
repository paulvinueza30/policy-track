"""FastAPI app entry point. Run: uvicorn app.main:app --reload"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.config import settings
from app.routers import account, districts, ai, health, members, policies, senators, states, votes

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
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", []) if p not in ("query", "path", "body"))
    return error_response(422, "validation_error", f"{where}: {first.get('msg', 'invalid request')}")


@app.exception_handler(Exception)
async def unexpected_error(_: Request, exc: Exception):
    return error_response(500, "internal_error", "Something went wrong on the server")


for router in (account.router, districts.router,health.router, states.router, members.router, senators.router, votes.router, policies.router, ai.router):
    app.include_router(router, prefix="/api")
