from gmail_reader import get_latest_email
from email_responder import generate_response
from send_email import send_email


def main():
    print("=== AI Email Human Review Workflow ===")

    print("\nRetrieving latest inbox email...")

    email = get_latest_email()

    if not email:
        print("No email found.")
        return

    subject = email["subject"]
    body = email["body"]

    print("\nEmail retrieved successfully.")

    print("\nGenerating AI response...")

    response = generate_response(subject, body)

    print("\n" + "=" * 60)
    print("AI-GENERATED RESPONSE")
    print("=" * 60)

    print(f"\nSubject: {response['subject']}")
    print(f"\nBody:\n{response['body']}")

    print("\n" + "=" * 60)

    confirmation = input(
        "\nSend this response? [y/N]: "
    ).strip().lower()

    if confirmation == "y":
        print("\nSending response...")

        # TODO: Replace with the sender address from the
        # retrieved Gmail message in a later step.
        recipient = email["sender"]

        print(f"\nSending response to: {recipient}")

        send_email(
            recipient,
            response["subject"],
            response["body"]
        )

        print("\nResponse sent successfully.")

    else:
        print("\nResponse cancelled. Nothing was sent.")


if __name__ == "__main__":
    main()