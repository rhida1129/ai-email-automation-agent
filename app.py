from email_generator import generate_email
from send_email import send_email


def main():
    print("=== AI Email Automation Agent ===\n")

    recipient = input("Recipient email address:\n> ")

    instruction = input(
        "\nWhat would you like the email to say?\n> "
    )

    print("\nGenerating email...")

    email = generate_email(instruction)

    print("\n" + "=" * 50)
    print("GENERATED EMAIL")
    print("=" * 50)

    print(f"\nTo: {recipient}")
    print(f"Subject: {email['subject']}")
    print(f"\n{email['body']}")

    print("\n" + "=" * 50)

    confirmation = input("\nSend this email? [y/N]: ").strip().lower()

    if confirmation == "y":
        print("\nSending email...")

        send_email(
            recipient,
            email["subject"],
            email["body"]
        )

        print("Email sent successfully.")

    else:
        print("\nEmail cancelled. Nothing was sent.")


if __name__ == "__main__":
    main()