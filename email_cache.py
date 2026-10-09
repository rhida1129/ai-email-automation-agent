
import sqlite3
from datetime import datetime


DATABASE_FILE = "email_cache.db"


def get_connection():
    """Create a connection to the local SQLite email database."""

    return sqlite3.connect(DATABASE_FILE)


def initialize_database():
    """Create the email cache and AI response draft tables."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS emails (
            message_id TEXT PRIMARY KEY,
            thread_id TEXT,
            sender TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT,
            category TEXT,
            classification_reason TEXT,
            retrieved_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS response_drafts (
            draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL UNIQUE,
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (message_id)
                REFERENCES emails (message_id)
        )
        """
    )

    connection.commit()
    connection.close()


# ============================================================
# EMAIL STORAGE
# ============================================================

def save_email(email):
    """Save one email without duplicating existing messages."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO emails (
            message_id,
            thread_id,
            sender,
            subject,
            body,
            category,
            classification_reason,
            retrieved_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            email.get("message_id"),
            email.get("thread_id"),
            email.get("sender", ""),
            email.get("subject", "(No Subject)"),
            email.get("body", ""),
            email.get("category"),
            email.get("classification_reason"),
            datetime.now().isoformat()
        )
    )

    connection.commit()
    connection.close()


def save_emails(emails):
    """Save multiple emails without duplicating existing messages."""

    if not emails:
        return

    connection = get_connection()
    cursor = connection.cursor()
    retrieved_at = datetime.now().isoformat()

    for email in emails:
        cursor.execute(
            """
            INSERT OR IGNORE INTO emails (
                message_id,
                thread_id,
                sender,
                subject,
                body,
                category,
                classification_reason,
                retrieved_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email.get("message_id"),
                email.get("thread_id"),
                email.get("sender", ""),
                email.get("subject", "(No Subject)"),
                email.get("body", ""),
                email.get("category"),
                email.get("classification_reason"),
                retrieved_at
            )
        )

    connection.commit()
    connection.close()


def get_cached_message_ids():
    """Return all Gmail message IDs stored locally."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT message_id FROM emails")
    rows = cursor.fetchall()

    connection.close()

    return {row[0] for row in rows}


def get_all_emails():
    """Return all cached emails, newest first."""

    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            message_id, thread_id, sender, subject, body,
            category, classification_reason, retrieved_at
        FROM emails
        ORDER BY retrieved_at DESC
        """
    )

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def get_emails_by_category(category):
    """Return cached emails in a specific category."""

    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            message_id, thread_id, sender, subject, body,
            category, classification_reason, retrieved_at
        FROM emails
        WHERE category = ?
        ORDER BY retrieved_at DESC
        """,
        (category,)
    )

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def update_email_category(
    message_id,
    category,
    classification_reason
):
    """Update an email's classification."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE emails
        SET category = ?, classification_reason = ?
        WHERE message_id = ?
        """,
        (
            category,
            classification_reason,
            message_id
        )
    )

    connection.commit()
    connection.close()


def get_uncategorized_emails():
    """Return emails that have not yet been classified."""

    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            message_id, thread_id, sender, subject, body,
            category, classification_reason, retrieved_at
        FROM emails
        WHERE category IS NULL OR category = ''
        ORDER BY retrieved_at DESC
        """
    )

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def get_email_by_id(message_id):
    """Retrieve one cached email by Gmail message ID."""

    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            message_id, thread_id, sender, subject, body,
            category, classification_reason, retrieved_at
        FROM emails
        WHERE message_id = ?
        """,
        (message_id,)
    )

    row = cursor.fetchone()
    connection.close()

    return dict(row) if row else None


def get_email_count():
    """Return the total number of cached emails."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM emails")
    count = cursor.fetchone()[0]

    connection.close()

    return count


# ============================================================
# AI RESPONSE DRAFT STORAGE
# ============================================================

def save_response_draft(
    message_id,
    recipient,
    subject,
    body
):
    """
    Save a generated response for human review.

    A new draft is created for an email, or its existing
    pending draft is updated. Reviewed or sent drafts
    cannot be overwritten by this function.
    """

    now = datetime.now().isoformat()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT status
        FROM response_drafts
        WHERE message_id = ?
        """,
        (message_id,)
    )

    existing = cursor.fetchone()

    if existing:
        if existing[0] != "pending":
            connection.close()

            raise ValueError(
                "This draft has already been reviewed or sent. "
                "It cannot be overwritten automatically."
            )

        cursor.execute(
            """
            UPDATE response_drafts
            SET recipient = ?,
                subject = ?,
                body = ?,
                updated_at = ?
            WHERE message_id = ?
            """,
            (
                recipient,
                subject,
                body,
                now,
                message_id
            )
        )

    else:
        cursor.execute(
            """
            INSERT INTO response_drafts (
                message_id,
                recipient,
                subject,
                body,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                message_id,
                recipient,
                subject,
                body,
                now,
                now
            )
        )

    connection.commit()
    connection.close()


def get_pending_response_drafts():
    """Return AI response drafts awaiting human review."""

    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            d.draft_id,
            d.message_id,
            d.recipient,
            d.subject,
            d.body,
            d.status,
            d.created_at,
            d.updated_at,
            e.sender AS original_sender,
            e.subject AS original_subject,
            e.category AS original_category
        FROM response_drafts AS d
        JOIN emails AS e
            ON e.message_id = d.message_id
        WHERE d.status = 'pending'
        ORDER BY d.created_at DESC
        """
    )

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def get_response_draft_by_email_id(message_id):
    """Retrieve the saved response draft for an email."""

    connection = get_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            draft_id, message_id, recipient, subject,
            body, status, created_at, updated_at
        FROM response_drafts
        WHERE message_id = ?
        """,
        (message_id,)
    )

    row = cursor.fetchone()
    connection.close()

    return dict(row) if row else None


def update_response_draft(
    message_id,
    recipient,
    subject,
    body
):
    """Edit a pending draft without changing its review status."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE response_drafts
        SET recipient = ?,
            subject = ?,
            body = ?,
            updated_at = ?
        WHERE message_id = ?
          AND status = 'pending'
        """,
        (
            recipient,
            subject,
            body,
            datetime.now().isoformat(),
            message_id
        )
    )

    updated = cursor.rowcount

    connection.commit()
    connection.close()

    return updated > 0


def update_response_draft_status(message_id, status):
    """Update a draft's workflow status."""

    allowed_statuses = {
        "pending",
        "approved",
        "rejected",
        "sent"
    }

    if status not in allowed_statuses:
        raise ValueError(
            f"Invalid draft status: {status}"
        )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE response_drafts
        SET status = ?, updated_at = ?
        WHERE message_id = ?
        """,
        (
            status,
            datetime.now().isoformat(),
            message_id
        )
    )

    updated = cursor.rowcount

    connection.commit()
    connection.close()

    return updated > 0


def get_response_draft_count(status=None):
    """Return the total number of drafts, optionally by status."""

    connection = get_connection()
    cursor = connection.cursor()

    if status is None:
        cursor.execute(
            "SELECT COUNT(*) FROM response_drafts"
        )
    else:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM response_drafts
            WHERE status = ?
            """,
            (status,)
        )

    count = cursor.fetchone()[0]
    connection.close()

    return count


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    print("=== Email Cache Test ===")

    initialize_database()

    print("SQLite database initialized successfully.")
    print(f"Cached emails: {get_email_count()}")
    print(
        "Pending response drafts: "
        f"{get_response_draft_count('pending')}"
    )