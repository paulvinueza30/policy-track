"""FastAPI dependencies shared by routers."""
from collections.abc import AsyncIterator

import httpx
from fastapi import HTTPException

from app.db import DatabaseNotConfigured, get_db
from app.db.repository import Repository
from app.services.http import make_client


def get_repo() -> Repository:
    try:
        return Repository(get_db())
    except DatabaseNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


async def get_http() -> AsyncIterator[httpx.AsyncClient]:
    async with make_client(timeout=15.0) as client:
        yield client
