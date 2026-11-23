"""Authentication: Google Sign-In (Google Identity Services) + guest mode.

Flow: the browser gets a Google ID token (JWT) -> POST /api/auth/google -> the backend verifies
the token's signature, audience and expiry with Google's public keys -> sets a signed session cookie.
If GOOGLE_CLIENT_ID is not configured, only guest mode is offered.
"""
from __future__ import annotations

import os
import uuid

from fastapi import HTTPException, Request

from . import db

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")


def verify_google_token(credential: str) -> dict:
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(400, "Google sign-in is not configured on the server (GOOGLE_CLIENT_ID missing)")
    try:
        from google.auth.transport import requests as g_requests
        from google.oauth2 import id_token

        info = id_token.verify_oauth2_token(credential, g_requests.Request(), GOOGLE_CLIENT_ID)
    except ValueError as exc:
        raise HTTPException(401, f"Invalid Google token: {exc}") from exc
    if not info.get("email_verified", False):
        raise HTTPException(401, "Google email not verified")
    return db.upsert_user("google:" + info["sub"], info.get("email", ""), info.get("name", "Trader"),
                          info.get("picture", ""), "google")


def guest_user() -> dict:
    uid = "guest:" + uuid.uuid4().hex[:12]
    return db.upsert_user(uid, "", "Guest Trader", "", "guest")


def current_user(request: Request) -> dict:
    uid = request.session.get("uid")
    user = db.get_user(uid) if uid else None
    if not user:
        raise HTTPException(401, "Not signed in")
    return user
