from collections.abc import Sequence
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64
from bs4 import BeautifulSoup
import html
import re


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


def _decode_gmail_body(data: str) -> str:
    padding = "=" * (-len(data) % 4)

    return base64.urlsafe_b64decode(
        data + padding
    ).decode("utf-8", errors="replace")


def _get_header(
    headers: list[dict[str, Any]],
    name: str,
) -> str | None:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value")

    return None

def _clean_email_text(text: str) -> str:
    # Decode HTML entities
    text = html.unescape(text)

    # Remove zero-width / invisible Unicode characters
    text = re.sub(
        r"[\u034f\u061c\u115f\u1160\u17b4\u17b5"
        r"\u180b-\u180f\u200b-\u200f\u202a-\u202e"
        r"\u2060-\u2064\u2066-\u206f\u2800\ufeff]",
        "",
        text,
    )

    # Remove soft-hyphen
    text = text.replace("\u00ad", "")

    # Remove non-breaking spaces
    text = text.replace("\xa0", " ")

    # Convert Markdown links:
    # [Read More](https://example.com)
    # -> Read More
    text = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        text,
    )

    # Convert bare markdown-style links that may have escaped :
    text = re.sub(
        r"\[([^\]]+)\]\(https?[^)]*\)",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )

    # Remove URLs entirely
    # If you want links in the final result, don't use this.
    text = re.sub(
        r"https?://\S+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove mailto links
    text = re.sub(
        r"mailto:\S+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove escaped URL artifacts
    text = text.replace(r"\:", ":")
    text = text.replace(r"\/", "/")

    # Normalize Windows newlines
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Collapse spaces
    text = re.sub(r"[ \t]+", " ", text)

    # Collapse excessive blank lines
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    return text.strip()

def _extract_email_body(payload: dict[str, Any]) -> str:
    plain_text = None
    html_text = None

    def walk_parts(part: dict[str, Any]) -> None:
        nonlocal plain_text, html_text

        mime_type = part.get("mimeType", "")
        data = part.get("body", {}).get("data")

        if data:
            try:
                decoded = _decode_gmail_body(data)
            except Exception:
                decoded = ""

            if mime_type == "text/plain" and decoded:
                plain_text = decoded

            elif mime_type == "text/html" and decoded:
                html_text = decoded

        for child in part.get("parts", []) or []:
            walk_parts(child)

    walk_parts(payload)

    if plain_text:
        return _clean_email_text(plain_text)

    if html_text:
        soup = BeautifulSoup(html_text, "html.parser")

        # Remove things that are almost always email noise
        for tag in soup([
            "script",
            "style",
            "noscript",
            "svg",
            "img",
        ]):
            tag.decompose()

        text = soup.get_text(
            separator="\n",
            strip=True,
        )

        return _clean_email_text(text)

    # Simple non-multipart email
    data = payload.get("body", {}).get("data")

    if data:
        try:
            return _clean_email_text(
                _decode_gmail_body(data)
            )
        except Exception:
            pass

    return ""


def _format_gmail_message(
    message: dict[str, Any],
) -> dict[str, Any]:

    payload = message.get("payload", {})
    headers = payload.get("headers", [])

    return {
        "from": _get_header(headers, "From"),
        "to": _get_header(headers, "To"),
        "subject": _get_header(headers, "Subject"),
        "date": _get_header(headers, "Date"),
        "body": _extract_email_body(payload),
    }


def read_gmail_messages(
    credentials: Credentials,
    *,
    query: str | None = None,
    max_results: int = 5,
    user_id: str = "me",
    label_ids: Sequence[str] | None = None,
    include_spam_trash: bool = False,
) -> list[dict[str, Any]]:

    if max_results < 1 or max_results > 500:
        raise ValueError(
            "max_results must be between 1 and 500."
        )

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

    response = (
        service.users()
        .messages()
        .list(**request)
        .execute()
    )

    messages = response.get("messages", [])

    def clean_email_html(html: str) -> str:
                soup = BeautifulSoup(html, "html.parser")
    
                # Remove images and tracking pixels
                for tag in soup.find_all(["img", "svg", "script", "style"]):
                    tag.decompose()
    
                # Remove links that are just tracking/redirect URLs
                for a in soup.find_all("a"):
                    text = a.get_text(" ", strip=True)
    
                    if text:
                        a.replace_with(text)
                    else:
                        a.decompose()
    
                return soup.get_text(
                separator="\n",
                strip=True,
            )
    
    results = []

    for message in messages:
        full_message = (
            service.users()
            .messages()
            .get(
                userId=user_id,
                id=message["id"],
                format="full",
            )
            .execute()
        )

        formatted_message = _format_gmail_message(full_message)
        formatted_message["body"] = clean_email_html(formatted_message["body"])
        
        results.append(formatted_message)

    return results


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


def _validate_event_time(
    field_name: str,
    value: dict[str, str],
) -> None:
    if not isinstance(value, dict):
        raise ValueError(
            f"{field_name} must be a dictionary."
        )

    date_time = value.get("dateTime")
    date = value.get("date")

    # Exactly one of dateTime/date must be supplied
    if bool(date_time) == bool(date):
        raise ValueError(
            f"{field_name} must include exactly one of "
            "'dateTime' or 'date'."
        )

    if date_time is not None:
        if not isinstance(date_time, str) or not date_time.strip():
            raise ValueError(
                f"{field_name}.dateTime must be a non-empty string."
            )

    if date is not None:
        if not isinstance(date, str) or not date.strip():
            raise ValueError(
                f"{field_name}.date must be a non-empty string."
            )