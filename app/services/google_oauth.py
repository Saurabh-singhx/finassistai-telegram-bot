import httpx
import secrets
import hashlib
import base64

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.config import settings


GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",

    # Gmail
    "https://www.googleapis.com/auth/gmail.readonly",

    # Calendar events (read and create meetings)
    "https://www.googleapis.com/auth/calendar.events",

    # Drive
    "https://www.googleapis.com/auth/drive.readonly",
]


def create_google_flow() -> Flow:
    if not settings.GOOGLE_CLIENT_ID:
        raise RuntimeError("GOOGLE_CLIENT_ID is not configured.")

    if not settings.GOOGLE_CLIENT_SECRET:
        raise RuntimeError("GOOGLE_CLIENT_SECRET is not configured.")

    if not settings.GOOGLE_REDIRECT_URI:
        raise RuntimeError("GOOGLE_REDIRECT_URI is not configured.")

    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [
                settings.GOOGLE_REDIRECT_URI,
            ],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=GOOGLE_SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )

    return flow

def generate_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(
        code_verifier.encode("ascii")
    ).digest()

    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

def generate_code_verifier() -> str:
    return secrets.token_urlsafe(64)

def get_authorization_url():
    """Create an authorization URL and the PKCE values needed for its callback."""
    state = secrets.token_urlsafe(32)
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    flow = create_google_flow()

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )

    return authorization_url, state, code_verifier


def exchange_code_for_credentials(
    code: str,
    code_verifier: str
) -> Credentials:
    """Exchange an authorization code, including the matching PKCE verifier."""
    flow = create_google_flow()
    # The authorization request includes a PKCE challenge. Google requires this
    # exact verifier at the token endpoint; without it the callback is rejected.
    flow.fetch_token(code=code, code_verifier=code_verifier)

    return flow.credentials


def credentials_to_data(
    credentials: Credentials,
) -> dict:

    return {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "expires_at": credentials.expiry,
        "scopes": list(credentials.scopes or []),
    }


async def get_google_user_info(
    credentials: Credentials,
) -> dict:

    async with httpx.AsyncClient(timeout=10) as client:

        response = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={
                "Authorization": f"Bearer {credentials.token}",
            },
        )

        response.raise_for_status()

        return response.json()
