"""Firestore access (AGENTS.md §5.1). Only the backend talks to Firestore."""
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore

from app.config import settings


@lru_cache
def get_db():
    if not firebase_admin._apps:
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": settings.firebase_project_id,
            "client_email": settings.firebase_client_email,
            "private_key": settings.firebase_private_key.replace("\\n", "\n"),
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        firebase_admin.initialize_app(cred)
    return firestore.client()
