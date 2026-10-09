import os
import json
import requests
from dotenv import load_dotenv


load_dotenv()

LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "http://localhost:1234/v1"
)

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "qwen/qwen3.5-9b"
)


def generate_response(subject, body):

    prompt = f"""
You are an AI email response assistant.

Write a professional and appropriate reply to the following email.

Email subject:
{subject}

Email body:
{body}

Return ONLY valid JSON in exactly this format:

{{
  "subject": "Re: original subject",
  "body": "Suggested response here"
}}

Requirements:
- Keep the original subject with "Re:".
- Write a professional response.
- Respond directly to the content of the email.
- Do not invent facts or commitments.
- Do not include markdown.
- Do not include code fences.
- Do not add explanations outside the JSON.
"""

    response = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        json={
            "model": LLM_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a professional email response "
                        "assistant."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7
        },
        timeout=120
    )

    response.raise_for_status()

    data = response.json()

    content = data["choices"][0]["message"]["content"]

    result = json.loads(content)

    if "subject" not in result:
        raise ValueError(
            "Generated response is missing a subject."
        )

    if "body" not in result:
        raise ValueError(
            "Generated response is missing a body."
        )

    return result


if __name__ == "__main__":
    print("=== AI Email Response Drafter ===\n")

    subject = input("Original email subject:\n> ")

    body = input("\nOriginal email body:\n> ")

    print("\nGenerating response...")

    result = generate_response(subject, body)

    print("\n" + "=" * 50)
    print("SUGGESTED RESPONSE")
    print("=" * 50)

    print(f"\nSubject: {result['subject']}")
    print(f"\nBody:\n{result['body']}")