"""Firestore access (AGENTS.md §5.1). Only the backend talks to Firestore."""
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore_async

from app.config import settings


class DatabaseNotConfigured(Exception):
    pass


def _app() -> firebase_admin.App:
    if firebase_admin._apps:
        return firebase_admin.get_app()
    if not (settings.firebase_project_id and settings.firebase_client_email and settings.firebase_private_key):
        raise DatabaseNotConfigured("Firebase credentials are not set (see backend/.env.example)")
    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": settings.firebase_project_id,
        "client_email": settings.firebase_client_email,
        "private_key": settings.firebase_private_key.replace("\\n", "\n"),
        "token_uri": "https://oauth2.googleapis.com/token",
    })
    return firebase_admin.initialize_app(cred)


@lru_cache
def get_db():
    """Async Firestore client."""
    return firestore_async.client(_app())
