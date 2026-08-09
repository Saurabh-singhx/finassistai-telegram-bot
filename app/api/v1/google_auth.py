from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.GoogleOAuthState import GoogleOAuthState
from app.models.user import User
from app.services.google_oauth import (
    credentials_to_data,
    exchange_code_for_credentials,
    get_authorization_url,
    get_google_user_info,
)

router = APIRouter(
    prefix="/auth/google",
    tags=["Google OAuth"],
)

@router.get("/start")
async def google_start(user_id: str):
    """
    Start Google OAuth for a specific FinAssist user.
    """

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(User).where(User.id == user_id)
        )

        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found.",
            )

        # Generate OAuth URL, state, and PKCE verifier
        authorization_url, google_state, code_verifier = (
            get_authorization_url()
        )

        oauth_state = GoogleOAuthState(
            state=google_state,
            user_id=user.id,
            code_verifier=code_verifier,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=10),
        )

        db.add(oauth_state)

        await db.commit()

    return {
        "authorization_url": authorization_url,
    }


@router.get("/callback")
async def google_callback(
    code: str,
    state: str,
):
    """
    Google redirects the user here after authorization.
    """

    async with AsyncSessionLocal() as db:

        # ---------------------------------------------------------
        # Find OAuth state
        # ---------------------------------------------------------

        result = await db.execute(
            select(GoogleOAuthState).where(
                GoogleOAuthState.state == state
            )
        )

        oauth_state = result.scalar_one_or_none()

        if not oauth_state:
            raise HTTPException(
                status_code=400,
                detail="Invalid OAuth state.",
            )

        # ---------------------------------------------------------
        # Check expiration
        # ---------------------------------------------------------

        if oauth_state.expires_at < datetime.now(timezone.utc):

            await db.delete(oauth_state)
            await db.commit()

            raise HTTPException(
                status_code=400,
                detail="OAuth session expired. Please try again.",
            )

        # ---------------------------------------------------------
        # Get user
        # ---------------------------------------------------------

        result = await db.execute(
            select(User).where(
                User.id == oauth_state.user_id
            )
        )

        user = result.scalar_one_or_none()

        if not user:
            await db.delete(oauth_state)
            await db.commit()

            raise HTTPException(
                status_code=404,
                detail="User not found.",
            )

        # ---------------------------------------------------------
        # Exchange authorization code for Google credentials
        # ---------------------------------------------------------

        try:
            credentials = exchange_code_for_credentials(
                code,
                oauth_state.code_verifier
            )

        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Google authorization failed: {exc}",
            )

        # ---------------------------------------------------------
        # Get Google profile
        # ---------------------------------------------------------

        try:
            google_user = await get_google_user_info(credentials)

        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Could not retrieve Google account: {exc}",
            )

        # ---------------------------------------------------------
        # Save Google account
        # ---------------------------------------------------------

        credential_data = credentials_to_data(credentials)

        user.google_id = google_user.get("sub")
        user.google_email = google_user.get("email")
        user.google_name = google_user.get("name")
        user.google_picture = google_user.get("picture")

        user.google_access_token = credential_data["access_token"]

        # Google may not return a refresh token on every
        # authorization. Never overwrite an existing one with None.
        if credential_data.get("refresh_token"):
            user.google_refresh_token = credential_data["refresh_token"]

        user.google_token_expires_at = credential_data["expires_at"]
        user.google_scopes = credential_data["scopes"]

        user.google_connected_at = (
            user.google_connected_at
            or datetime.now(timezone.utc)
        )

        user.google_updated_at = datetime.now(timezone.utc)

        # ---------------------------------------------------------
        # Delete used OAuth state
        # ---------------------------------------------------------

        await db.delete(oauth_state)

        await db.commit()

    return {
        "success": True,
        "message": "Google account connected successfully.",
        "email": user.google_email,
    }
