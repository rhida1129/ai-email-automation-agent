
import requests
from collections import Counter
from email.utils import parseaddr

from gmail_reader import sync_inbox

from email_cache import (
    get_uncategorized_emails,
    update_email_category,
    get_all_emails,
    get_response_draft_by_email_id,
    save_response_draft
)

from email_classifier import classify_email
from email_responder import generate_response


# ============================================================
# CONFIGURATION
# ============================================================

CLASSIFICATION_BATCH_SIZE = 10
RESPONSE_DRAFT_BATCH_SIZE = 3
GMAIL_SYNC_BATCH_SIZE = 100

VALID_CATEGORIES = {
    "Work",
    "Personal",
    "Promotional",
    "Transactional",
    "Urgent"
}

DRAFT_ELIGIBLE_CATEGORIES = {
    "Work",
    "Personal",
    "Urgent"
}


# ============================================================
# AUTOMATED EMAIL FILTERS
# ============================================================

AUTOMATED_SENDER_KEYWORDS = [
    "no-reply",
    "noreply",
    "do-not-reply",
    "donotreply",
    "mailer-daemon",
    "newsletter",
    "marketing",
    "notifications",
    "notification"
]

AUTOMATED_SUBJECT_KEYWORDS = [
    "verification code",
    "verification link",
    "one-time password",
    "one time password",
    "security alert",
    "login code",
    "sign-in alert",
    "password reset",
    "password recovery",
    "secure link to log in",
    "secure link to login",
    "verification required",
    "receipt",
    "order confirmation",
    "purchase confirmation",
    "delivery notification",
    "shipping confirmation",
    "payment confirmation",
    "subscription confirmation",
    "newsletter",
    "unsubscribe",
    "discount",
    "coupon",
    "flash sale",
    "promotional offer",
    "weekly digest",
    "daily digest",
    "personal update",
    "5-star rider",
    "five-star rider",
    "trip receipt",
    "ride receipt"
]


def get_response_draft_skip_reason(email):
    """
    Return a reason when an email should not receive a reply draft.
    Return None when the email passes these checks.
    """

    sender = (email.get("sender") or "").lower()
    subject = (email.get("subject") or "").lower()
    category = email.get("category")
    body = email.get("body") or ""

    if category not in DRAFT_ELIGIBLE_CATEGORIES:
        return "ineligible category"

    if any(keyword in sender for keyword in AUTOMATED_SENDER_KEYWORDS):
        return "automated or marketing sender"

    if any(keyword in subject for keyword in AUTOMATED_SUBJECT_KEYWORDS):
        return "automated or promotional subject"

    if not body.strip():
        return "empty email body"

    return None


# ============================================================
# AI CLASSIFICATION
# ============================================================

def classify_uncategorized_emails(
    batch_size=CLASSIFICATION_BATCH_SIZE
):
    uncategorized_emails = get_uncategorized_emails()

    if not uncategorized_emails:
        print("\nNo uncategorized emails found.")
        return 0

    emails_to_classify = uncategorized_emails[:batch_size]

    successful = 0
    failed = 0

    print(
        f"\nFound {len(uncategorized_emails)} "
        "uncategorized email(s)."
    )
    print(
        f"Classifying the next "
        f"{len(emails_to_classify)} email(s)..."
    )

    for index, email in enumerate(emails_to_classify, start=1):
        subject = email.get("subject") or "(No Subject)"
        body = email.get("body") or ""

        print(
            f"\nClassifying {index}/{len(emails_to_classify)}: "
            f"{subject}"
        )

        classification = None

        # First attempt
        try:
            classification = classify_email(subject, body)

        except requests.exceptions.Timeout:
            print("AI request timed out.")

        except requests.exceptions.RequestException as error:
            print(f"AI request failed: {error}")

        except Exception as error:
            print(f"Classification error: {error}")

        # Retry once when classification fails
        if classification is None:
            print("Retrying classification once...")

            try:
                classification = classify_email(subject, body)

            except requests.exceptions.Timeout:
                print("Retry also timed out.")

            except requests.exceptions.RequestException as error:
                print(f"Retry failed: {error}")

            except Exception as error:
                print(f"Retry classification error: {error}")

        if classification is None:
            failed += 1
            print(
                "Skipping this email. "
                "It will remain uncategorized."
            )
            continue

        category = classification.get("category")
        reason = classification.get("reason", "")

        if category not in VALID_CATEGORIES:
            failed += 1
            print(f"Invalid category returned by AI: {category}")
            continue

        try:
            update_email_category(
                email["message_id"],
                category,
                reason
            )

            print(f"Category: {category}")
            print(f"Reason: {reason}")
            successful += 1

        except Exception as error:
            failed += 1
            print(f"Failed to save classification: {error}")

    print("\n" + "=" * 60)
    print("CLASSIFICATION SUMMARY")
    print("=" * 60)
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    return successful


# ============================================================
# AI RESPONSE DRAFT GENERATION
# ============================================================

def generate_response_drafts(
    batch_size=RESPONSE_DRAFT_BATCH_SIZE
):
    """
    Generate a limited number of response drafts.
    All drafts remain subject to human review.
    """

    emails = get_all_emails()

    if not emails:
        print("\nNo cached emails available for drafting.")
        return 0

    generated = 0
    failed = 0
    examined = 0
    skip_reasons = Counter()

    print("\nSearching for emails suitable for reply drafts...")
    print(f"Cached emails available: {len(emails)}")
    print(f"Maximum drafts for this run: {batch_size}")

    for email in emails:
        if generated >= batch_size:
            break

        examined += 1
        message_id = email.get("message_id")

        if not message_id:
            skip_reasons["missing message ID"] += 1
            continue

        # Never recreate an existing draft, including drafts
        # that have already been approved, rejected, or sent.
        try:
            existing_draft = get_response_draft_by_email_id(
                message_id
            )

        except Exception as error:
            failed += 1
            print(f"Could not check existing draft: {error}")
            continue

        if existing_draft:
            skip_reasons["draft already exists"] += 1
            continue

        skip_reason = get_response_draft_skip_reason(email)

        if skip_reason:
            skip_reasons[skip_reason] += 1
            continue

        sender = email.get("sender") or ""
        recipient = parseaddr(sender)[1]

        if not recipient:
            skip_reasons["unrecognized sender address"] += 1
            continue

        subject = email.get("subject") or "(No Subject)"
        body = email.get("body") or ""

        print(f"\nGenerating reply draft: {subject}")

        try:
            response = generate_response(subject, body)

            draft_subject = response.get("subject")
            draft_body = response.get("body")

            if not draft_subject or not draft_body:
                raise ValueError(
                    "The AI returned an incomplete response draft."
                )

        except requests.exceptions.Timeout:
            failed += 1
            print("Reply generation timed out; no draft was saved.")
            continue

        except requests.exceptions.RequestException as error:
            failed += 1
            print(f"Reply generation request failed: {error}")
            continue

        except Exception as error:
            failed += 1
            print(f"Could not generate reply draft: {error}")
            continue

        try:
            save_response_draft(
                message_id=message_id,
                recipient=recipient,
                subject=draft_subject,
                body=draft_body
            )

            generated += 1
            print("Reply draft saved for human review.")

        except Exception as error:
            failed += 1
            print(f"Failed to save reply draft: {error}")

    print("\n" + "=" * 60)
    print("RESPONSE DRAFT SUMMARY")
    print("=" * 60)
    print(f"Cached emails available: {len(emails)}")
    print(f"Emails examined: {examined}")
    print(f"Drafts generated: {generated}")
    print(f"Failures: {failed}")

    print("\nSkip breakdown:")
    if skip_reasons:
        for reason, count in skip_reasons.most_common():
            print(f"  {reason}: {count}")
    else:
        print("  No emails skipped.")

    print("\nAutomatic email sending: DISABLED")
    return generated


# ============================================================
# AUTOMATION WORKER
# ============================================================

def run_automation():
    print("=" * 60)
    print("AI EMAIL AUTOMATION WORKER")
    print("=" * 60)

    # Step 1: Sync Gmail
    print("\n[1/3] Checking Gmail for new emails...")

    try:
        new_emails = sync_inbox(
            batch_size=GMAIL_SYNC_BATCH_SIZE
        )

        if new_emails:
            print(f"\nNew emails added: {len(new_emails)}")
        else:
            print("\nNo new emails found.")

    except Exception as error:
        print(f"\nGmail sync failed: {error}")
        return

    # Step 2: Classify the next batch
    print("\n[2/3] Classifying uncategorized emails...")

    classify_uncategorized_emails(
        batch_size=CLASSIFICATION_BATCH_SIZE
    )

    # Step 3: Generate drafts from cached emails
    print("\n[3/3] Generating reply drafts...")

    generate_response_drafts(
        batch_size=RESPONSE_DRAFT_BATCH_SIZE
    )

    print("\nAutomation cycle completed.")
    print("No emails were sent automatically.")


# ============================================================
# MANUAL TEST
# ============================================================

if __name__ == "__main__":
    run_automation()