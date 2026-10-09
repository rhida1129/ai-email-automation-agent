import base64
from email.message import EmailMessage

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TOKEN_FILE = "token.json"


def send_email(to_email, subject, body):
    credentials = Credentials.from_authorized_user_file(
        TOKEN_FILE,
        SCOPES
    )

    gmail_service = build(
        "gmail",
        "v1",
        credentials=credentials
    )

    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    message_body = {
        "raw": encoded_message
    }

    result = gmail_service.users().messages().send(
        userId="me",
        body=message_body
    ).execute()

    print(f"Email sent successfully. Message ID: {result['id']}")


if __name__ == "__main__":
    print(
        "Email sending function is ready. "
        "Call send_email(to_email, subject, body) "
        "with an explicitly provided recipient."
    )