from gmail_reader import get_latest_email
from email_responder import generate_response


def main():
    print("=== AI Inbox Response Drafter ===")

    print("\nRetrieving latest inbox email...")

    email = get_latest_email()

    if not email:
        print("No email found.")
        return

    subject = email["subject"]
    body = email["body"]

    print("\nEmail retrieved successfully.")

    print("\n" + "=" * 50)
    print("INCOMING EMAIL")
    print("=" * 50)

    print(f"\nSubject: {subject}")
    print(f"\nBody:\n{body}")

    print("\nGenerating AI response...")

    response = generate_response(subject, body)

    print("\n" + "=" * 50)
    print("SUGGESTED RESPONSE")
    print("=" * 50)

    print(f"\nSubject: {response['subject']}")
    print(f"\nBody:\n{response['body']}")


if __name__ == "__main__":
    main()