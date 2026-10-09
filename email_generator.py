import os
import json
import requests
from dotenv import load_dotenv


load_dotenv()

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:1234/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen/qwen3.5-9b")


def generate_email(instruction):
    prompt = f"""
You are an AI email assistant.

Generate a professional email based on the user's instruction.

User instruction:
{instruction}

Return ONLY valid JSON in exactly this format:

{{
  "subject": "Email subject here",
  "body": "Email body here"
}}

Do not include markdown.
Do not include code fences.
Do not add any explanation outside the JSON.
"""

    response = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        json={
            "model": LLM_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional email-writing assistant."
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

    # Convert the model's JSON text into a Python dictionary
    email_data = json.loads(content)

    # Validate the required fields
    if "subject" not in email_data:
        raise ValueError("Generated email is missing a subject.")

    if "body" not in email_data:
        raise ValueError("Generated email is missing a body.")

    return email_data


if __name__ == "__main__":
    instruction = input(
        "What email would you like the AI to write?\n> "
    )

    result = generate_email(instruction)

    print("\nGenerated Email:")
    print(f"Subject: {result['subject']}")
    print(f"\nBody:\n{result['body']}")