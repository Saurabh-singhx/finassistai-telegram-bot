from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def build_gmail_service(credentials: Credentials):
    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )


def build_calendar_service(credentials: Credentials):
    return build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def build_drive_service(credentials: Credentials):
    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )
