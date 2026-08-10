from collections.abc import Sequence
from typing import Any

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


def read_gmail_messages(
    credentials: Credentials,
    *,
    query: str | None = None,
    max_results: int = 10,
    user_id: str = "me",
    label_ids: Sequence[str] | None = None,
    include_spam_trash: bool = False,
) -> list[dict[str, Any]]:
    """Return full Gmail messages matching the supplied filters.

    Gmail's ``messages.list`` endpoint returns only IDs, so each matching ID is
    fetched with ``messages.get`` before it is returned.  The result therefore
    includes headers, snippet, labels, and MIME payload data.
    """
    if max_results < 1 or max_results > 500:
        raise ValueError("max_results must be between 1 and 500.")

    service = build_gmail_service(credentials)
    request: dict[str, Any] = {
        "userId": user_id,
        "maxResults": max_results,
        "includeSpamTrash": include_spam_trash,
    }
    if query:
        request["q"] = query
    if label_ids:
        request["labelIds"] = list(label_ids)

    response = service.users().messages().list(**request).execute()
    messages = response.get("messages", [])

    return [
        service.users().messages().get(userId=user_id, id=message["id"], format="full").execute()
        for message in messages
    ]


def list_calendar_events(
    credentials: Credentials,
    *,
    calendar_id: str = "primary",
    time_min: str | None = None,
    time_max: str | None = None,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Return events from a calendar, optionally constrained to an RFC3339 range."""
    if max_results < 1 or max_results > 2500:
        raise ValueError("max_results must be between 1 and 2500.")
    if time_min and time_max and time_min > time_max:
        raise ValueError("time_min must be earlier than or equal to time_max.")

    request: dict[str, Any] = {
        "calendarId": calendar_id,
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": max_results,
    }
    if time_min:
        request["timeMin"] = time_min
    if time_max:
        request["timeMax"] = time_max

    response = build_calendar_service(credentials).events().list(**request).execute()
    return response.get("items", [])


def create_calendar_event(
    credentials: Credentials,
    *,
    summary: str,
    start: dict[str, str],
    end: dict[str, str],
    calendar_id: str = "primary",
    description: str | None = None,
    location: str | None = None,
    attendees: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Create and return a Calendar event.

    ``start`` and ``end`` must each include either ``dateTime`` (RFC3339) or
    ``date`` (all-day event).  A ``timeZone`` field may also be supplied.
    """
    if not summary.strip():
        raise ValueError("summary must not be empty.")
    _validate_event_time("start", start)
    _validate_event_time("end", end)

    event: dict[str, Any] = {
        "summary": summary,
        "start": dict(start),
        "end": dict(end),
    }
    if description is not None:
        event["description"] = description
    if location is not None:
        event["location"] = location
    if attendees:
        event["attendees"] = [{"email": email} for email in attendees]

    return build_calendar_service(credentials).events().insert(
        calendarId=calendar_id,
        body=event,
        sendUpdates="all" if attendees else "none",
    ).execute()


def _validate_event_time(field_name: str, value: dict[str, str]) -> None:
    if not isinstance(value, dict) or not (value.get("dateTime") or value.get("date")):
        raise ValueError(f"{field_name} must include either 'dateTime' or 'date'.")
