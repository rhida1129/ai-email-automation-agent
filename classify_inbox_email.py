from gmail_reader import get_latest_email
from email_classifier import classify_email


def main():
    print("=== AI Email Inbox Classifier ===")

    print("\nRetrieving latest inbox email...")

    email = get_latest_email()

    if not email:
        print("No email found.")
        return

    subject = email["subject"]
    body = email["body"]

    print("\nEmail retrieved successfully.")
    print(f"\nSubject: {subject}")

    print("\nClassifying email...")

    result = classify_email(subject, body)

    print("\n" + "=" * 50)
    print("AI CLASSIFICATION")
    print("=" * 50)

    print(f"\nCategory: {result['category']}")
    print(f"Reason: {result['reason']}")


if __name__ == "__main__":
    main()