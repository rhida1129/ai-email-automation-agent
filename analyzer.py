import os

import requests
from dotenv import load_dotenv

load_dotenv()

LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")


def call_llm(prompt: str) -> str:
    response = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        json={
            "model": LLM_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0.2,
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    return data["choices"][0]["message"]["content"]
if __name__ == "__main__":
    result = call_llm("Say hello and confirm that you are ready to analyze emails.")
    print(result)