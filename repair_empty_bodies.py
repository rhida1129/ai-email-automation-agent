import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from gmail_reader import get_gmail_service, get_message_with_retry, parse_email
from email_cache import DATABASE_FILE


BATCH_SIZE = 50
BACKUP_SUFFIX = datetime.now().strftime("%Y%m%d_%H%M%S")


def main():
    database_path = Path(DATABASE_FILE)

    if not database_path.exists():
        print(f"Database not found: {database_path.resolve()}")
        return

    # Back up the database before making any changes.
    backup_path = database_path.with_name(
        f"{database_path.stem}_backup_{BACKUP_SUFFIX}{database_path.suffix}"
    )
    shutil.copy2(database_path, backup_path)

    print(f"Database backup created: {backup_path}")
    print("Checking cached emails with empty bodies...")

    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row

    try:
        rows = connection.execute(
            """
            SELECT message_id, subject
            FROM emails
            WHERE body IS NULL OR TRIM(body) = ''
            ORDER BY retrieved_at DESC
            """
        ).fetchall()

        print(f"Empty-body messages found: {len(rows)}")

        if not rows:
            print("Nothing to repair.")
            return

        service = get_gmail_service()

        repaired = 0
        still_empty = 0
        failed = 0

        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start:start + BATCH_SIZE]

            for row in batch:
                message_id = row["message_id"]

                try:
                    message = get_message_with_retry(
                        service,
                        message_id
                    )
                    email = parse_email(message)
                    body = (email.get("body") or "").strip()

                    if not body:
                        still_empty += 1
                        print(f"Still empty: {row['subject']}")
                        continue

                    # Update ONLY the body column.
                    connection.execute(
                        """
                        UPDATE emails
                        SET body = ?
                        WHERE message_id = ?
                          AND (body IS NULL OR TRIM(body) = '')
                        """,
                        (body, message_id)
                    )
                    repaired += connection.execute(
                        "SELECT changes()"
                    ).fetchone()[0]

                except Exception as error:
                    failed += 1
                    print(
                        f"Failed: {row['subject']} "
                        f"({message_id}): {error}"
                    )

            # Commit after each batch so progress is preserved.
            connection.commit()

            processed = min(start + len(batch), len(rows))
            print(
                f"Progress: {processed}/{len(rows)} "
                f"| repaired: {repaired} "
                f"| still empty: {still_empty} "
                f"| failed: {failed}"
            )

        remaining = connection.execute(
            """
            SELECT COUNT(*)
            FROM emails
            WHERE body IS NULL OR TRIM(body) = ''
            """
        ).fetchone()[0]

        print("\n=== Repair Summary ===")
        print(f"Initially empty: {len(rows)}")
        print(f"Bodies repaired: {repaired}")
        print(f"Still empty: {still_empty}")
        print(f"Fetch/processing failures: {failed}")
        print(f"Empty bodies remaining in database: {remaining}")
        print(f"Backup: {backup_path.resolve()}")

    finally:
        connection.close()


if __name__ == "__main__":
    main()