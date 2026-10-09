
import base64
import re
import time
from html import unescape

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

from email_cache import (
    initialize_database,
    get_cached_message_ids,
    save_emails,
    get_email_count,
)


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_FILE = "gmail_read_token.json"


def get_gmail_service():
    """Create an authenticated Gmail API service."""
    credentials = Credentials.from_authorized_user_file(
        TOKEN_FILE,
        SCOPES,
    )
    return build("gmail", "v1", credentials=credentials)


def get_email_body(payload):
    """
    Extract readable email text from Gmail API MIME payloads.
    Prefer plain text and fall back to HTML.
    """

    if not payload:
        return ""

    def decode_body(data):
        if not data:
            return ""

        # Gmail uses URL-safe Base64 and may omit padding.
        data += "=" * (-len(data) % 4)

        try:
            decoded = base64.urlsafe_b64decode(data)
            return decoded.decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            return ""

    def html_to_text(html):
        html = re.sub(
            r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>",
            " ",
            html,
        )
        html = re.sub(
            r"(?i)<br\s*/?\s*>|</(?:p|div|li|tr|h[1-6])\s*>",
            "\n",
            html,
        )
        html = re.sub(r"(?s)<[^>]+>", " ", html)
        html = unescape(html)
        html = re.sub(r"[ \t]+", " ", html)
        html = re.sub(r" *\n *", "\n", html)
        return html.strip()

    mime_type = payload.get("mimeType", "").lower()
    body_data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        return decode_body(body_data)

    parts = payload.get("parts", [])

    # Prefer plain text, including nested MIME parts.
    for part in parts:
        if part.get("mimeType", "").lower() == "text/plain":
            body = get_email_body(part)
            if body.strip():
                return body

        if part.get("parts"):
            body = get_email_body(part)
            if body.strip():
                return body

    if mime_type == "text/html" and body_data:
        return html_to_text(decode_body(body_data))

    # Fall back to any readable body in multipart messages.
    for part in parts:
        body = get_email_body(part)
        if body.strip():
            return body

    if body_data:
        return decode_body(body_data)

    return ""


def get_header(headers, name):
    """Return a header value without regard to header-name casing."""
    for header in headers or []:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def clean_sender(sender):
    """Extract the email address from a sender header when possible."""
    if not sender:
        return ""

    match = re.search(r"<([^<>]+)>", sender)
    if match:
        return match.group(1).strip()

    return sender.strip()


def get_message_with_retry(service, message_id, max_retries=5):
    """Retrieve a Gmail message, retrying rate-limit errors."""
    for attempt in range(max_retries):
        try:
            return (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
        except HttpError as error:
            status = getattr(error.resp, "status", None)
            error_text = str(error).lower()

            is_rate_limit = (
                status == 429
                or "ratelimitexceeded" in error_text
                or "rate limit" in error_text
            )

            if not is_rate_limit or attempt == max_retries - 1:
                raise

            delay = min(2 ** attempt, 30)
            print(
                f"Rate limit reached for {message_id}. "
                f"Retrying in {delay} seconds..."
            )
            time.sleep(delay)


def parse_email(message):
    """Convert a Gmail API message into the project's email dictionary."""
    payload = message.get("payload", {})
    headers = payload.get("headers", [])

    sender_header = get_header(headers, "From")
    body = get_email_body(payload)

    return {
        "message_id": message.get("id", ""),
        "thread_id": message.get("threadId", ""),
        "subject": get_header(headers, "Subject") or "(No Subject)",
        "sender": clean_sender(sender_header),
        "body": body,
    }


def get_inbox_batch(batch_size=100, exclude_message_ids=None):
    """Fetch a batch of Inbox messages not already cached."""
    service = get_gmail_service()
    exclude_message_ids = set(exclude_message_ids or [])
    emails = []
    page_token = None

    try:
        while len(emails) < batch_size:
            remaining = batch_size - len(emails)

            response = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    labelIds=["INBOX"],
                    maxResults=min(remaining, 100),
                    pageToken=page_token,
                )
                .execute()
            )

            messages = response.get("messages", [])
            if not messages:
                break

            for item in messages:
                message_id = item["id"]

                if message_id in exclude_message_ids:
                    continue

                try:
                    message = get_message_with_retry(service, message_id)
                    emails.append(parse_email(message))
                    print(
                        f"Retrieved {len(emails)}/{batch_size}: "
                        f"{emails[-1]['subject']}"
                    )
                except Exception as error:
                    print(f"Failed to retrieve {message_id}: {error}")

                if len(emails) >= batch_size:
                    break

                time.sleep(0.1)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

    except HttpError as error:
        print(f"Gmail API error while reading Inbox: {error}")

    return emails


def sync_inbox(batch_size=100):
    """Fetch and cache new Inbox messages."""
    initialize_database()

    cached_ids = get_cached_message_ids()
    print(f"Cached message IDs: {len(cached_ids)}")

    emails = get_inbox_batch(
        batch_size=batch_size,
        exclude_message_ids=cached_ids,
    )

    if emails:
        save_emails(emails)

    total = get_email_count()
    print(f"New messages retrieved: {len(emails)}")
    print(f"Total cached emails: {total}")

    return emails


def get_inbox_emails(max_results=20):
    """Return a limited number of recent Inbox messages."""
    service = get_gmail_service()
    emails = []

    try:
        response = (
            service.users()
            .messages()
            .list(
                userId="me",
                labelIds=["INBOX"],
                maxResults=max_results,
            )
            .execute()
        )

        for item in response.get("messages", []):
            try:
                message = get_message_with_retry(service, item["id"])
                emails.append(parse_email(message))
            except Exception as error:
                print(f"Failed to retrieve {item['id']}: {error}")

    except HttpError as error:
        print(f"Gmail API error: {error}")

    return emails


def get_latest_email():
    """Return the most recent Inbox email, or None if unavailable."""
    emails = get_inbox_emails(max_results=1)
    return emails[0] if emails else None


if __name__ == "__main__":
    print("=== Gmail Inbox Sync ===")
    sync_inbox(batch_size=100)