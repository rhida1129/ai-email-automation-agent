import os
import json
import requests
from dotenv import load_dotenv


load_dotenv()

LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "http://localhost:1234/v1"
).rstrip("/")

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "qwen/qwen3.5-9b"
)

REQUEST_TIMEOUT = 120
MAX_BODY_CHARS = 12000

ALLOWED_CATEGORIES = {
    "Work",
    "Personal",
    "Promotional",
    "Transactional",
    "Urgent"
}


SYSTEM_PROMPT = """
You are a careful email classification assistant.

Classify emails based on their actual purpose and content, not just
the sender's name, the presence of a person's name, or the subject.

CATEGORY DEFINITIONS

1. Work
Use for genuine professional correspondence, such as messages from
colleagues, clients, recruiters, supervisors, or professional contacts.
A message is not Work merely because it mentions a job, course, meeting,
software product, or professional topic.

2. Personal
Use for genuine personal correspondence, such as messages from
friends, family, or people communicating directly with the recipient.
Automated account notifications and purchase receipts are not Personal
just because they contain the recipient's name.

3. Transactional
Use for automated messages that confirm, document, or report an action,
event, or status involving the recipient or their account.

Examples include:
- receipts and invoices
- purchase confirmations
- ride receipts
- order confirmations
- delivery updates
- booking confirmations
- payment confirmations
- appointment confirmations
- account activity notifications
- password reset emails
- verification emails
- subscription or billing notifications

Transactional emails are not Promotional merely because they contain
a link to an app, website, or service.

Do not classify a transactional email as Urgent unless the content
clearly indicates that immediate action is required.

4. Promotional
Use for advertising, marketing, newsletters, product recommendations,
discounts, coupons, sales, referral offers, promotional competitions,
marketing digests, and messages encouraging purchases or subscriptions.

5. Urgent
Use only when the content indicates a time-sensitive matter requiring
prompt attention, such as an urgent request from a person, a critical
work issue, or a serious time-sensitive problem.

A verification code, login link, routine security notification, or
automated alert is not automatically Urgent.

IMPORTANT DISTINCTIONS

- Automated messages are not automatically genuine correspondence.
- Login links, one-time codes, receipts, delivery updates, meeting
  attendance notifications, account activity notices, and routine
  service notifications should not be classified as Work or Personal
  solely because they concern an account or service.
- Receipts, confirmations, invoices, and routine service notifications
  should generally be classified as Transactional.
- A marketing email remains Promotional even if it mentions work,
  education, technology, jobs, or the recipient by name.
- A genuine message from a colleague or friend can still be Work or
  Personal even if it contains links.
- Do not invent facts about the sender or the email.
- If the message's purpose is unclear, use the best-supported category
  and explain the uncertainty briefly.
- Base the classification on the subject and body supplied. Do not
  assume that a message needs a reply just because it is Work,
  Personal, or Urgent.

Return only one JSON object with exactly these keys:
"category" and "reason".

The category must be exactly one of:
Work, Personal, Promotional, Transactional, Urgent.

The reason must briefly explain the classification using evidence
from the email. Do not claim details that are not present.
Do not return markdown or code fences.
"""


def _get_lm_studio_root():
    """
    Convert http://localhost:1234/v1 into http://localhost:1234
    for LM Studio's native REST API.
    """
    if LLM_BASE_URL.endswith("/v1"):
        return LLM_BASE_URL[:-3]

    return LLM_BASE_URL


def _content_to_text(content):
    """Convert common LM Studio content formats into plain text."""
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, str):
                parts.append(item)

            elif isinstance(item, dict):
                text_value = item.get("text")

                if isinstance(text_value, str):
                    parts.append(text_value)

        return "\n".join(parts).strip()

    return ""


def _extract_native_response(data):
    """Extract generated text from LM Studio's native REST response."""
    output_items = data.get("output", [])

    if not isinstance(output_items, list):
        return "", "The native API returned an unexpected output format."

    message_parts = []
    reasoning_length = 0
    output_types = []

    for item in output_items:
        if not isinstance(item, dict):
            continue

        item_type = item.get("type")
        output_types.append(str(item_type))

        if item_type == "message":
            text_value = _content_to_text(item.get("content"))

            if text_value:
                message_parts.append(text_value)

        elif item_type == "reasoning":
            reasoning = _content_to_text(item.get("content"))
            reasoning_length += len(reasoning)

    content = "\n".join(message_parts).strip()

    if content:
        return content, ""

    diagnostic = (
        "LM Studio's native API returned no message text. "
        f"Output types: {output_types}; "
        f"reasoning characters: {reasoning_length}."
    )

    return "", diagnostic


def _request_native_api(user_prompt):
    """
    Request a response with reasoning disabled.

    This is the preferred path for LM Studio versions that support
    POST /api/v1/chat and its reasoning setting.
    """
    url = f"{_get_lm_studio_root()}/api/v1/chat"

    payload = {
        "model": LLM_MODEL,
        "system_prompt": SYSTEM_PROMPT,
        "input": user_prompt,
        "temperature": 0,
        "max_output_tokens": 400,
        "reasoning": "off",
        "stream": False,
        "store": False
    }

    response = requests.post(
        url,
        json=payload,
        timeout=REQUEST_TIMEOUT
    )

    # An older LM Studio version may not support this endpoint or
    # may reject one of its parameters. In that case, try the
    # OpenAI-compatible endpoint instead.
    if response.status_code in {400, 404, 405, 422}:
        return "", (
            "Native API unavailable or rejected the request: "
            f"HTTP {response.status_code}: {response.text[:300]}"
        )

    response.raise_for_status()

    try:
        data = response.json()
    except ValueError as error:
        raise ValueError(
            "LM Studio's native API returned invalid JSON."
        ) from error

    return _extract_native_response(data)


def _request_openai_compatible_api(user_prompt):
    """
    Compatibility fallback for LM Studio's /v1/chat/completions API.

    A larger token budget gives reasoning models more opportunity to
    finish reasoning and produce their final answer.
    """
    url = f"{LLM_BASE_URL}/chat/completions"

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 1200,
        "stream": False,
        "chat_template_kwargs": {
            "enable_thinking": False
        }
    }

    response = requests.post(
        url,
        json=payload,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    try:
        data = response.json()
        choices = data.get("choices", [])

        if not choices or not isinstance(choices[0], dict):
            raise ValueError("The response contains no valid choices.")

        choice = choices[0]
        message = choice.get("message", {})

        if not isinstance(message, dict):
            raise ValueError("The response contains no valid message.")

    except (ValueError, TypeError, KeyError) as error:
        raise ValueError(
            "LM Studio returned an unexpected response format "
            "from the OpenAI-compatible endpoint."
        ) from error

    content = _content_to_text(message.get("content"))

    if content:
        return content

    # Do not mistake internal reasoning for a completed classification.
    reasoning = message.get("reasoning_content")

    if not isinstance(reasoning, str) or not reasoning:
        reasoning = message.get("reasoning")

    reasoning_length = (
        len(reasoning) if isinstance(reasoning, str) else 0
    )

    finish_reason = choice.get("finish_reason", "unknown")

    raise ValueError(
        "LM Studio returned empty message content from the "
        "OpenAI-compatible endpoint. "
        f"Finish reason: {finish_reason}. "
        f"Reasoning characters: {reasoning_length}. "
        "The model may be using its token budget for reasoning. "
        "Check the LM Studio model's prompt template and version."
    )


def _request_model(user_prompt):
    """
    Try the native API first, then fall back to the compatible API
    when the native endpoint is unavailable or produces no text.
    """
    native_diagnostic = ""

    try:
        content, native_diagnostic = _request_native_api(user_prompt)

        if content:
            return content

    except requests.exceptions.RequestException:
        # Network errors and timeouts should be reported directly.
        # Retrying another endpoint in this case may just repeat
        # a long wait or send another request to an unavailable server.
        raise

    except ValueError as error:
        native_diagnostic = str(error)

    try:
        return _request_openai_compatible_api(user_prompt)

    except Exception as error:
        raise RuntimeError(
            "Classification failed on both LM Studio API paths.\n"
            f"Native API result: {native_diagnostic or 'No usable text.'}\n"
            f"Compatibility API result: {error}"
        ) from error


def _parse_json_result(content):
    """Parse the JSON object returned by the model."""
    content = content.strip()

    # Remove a surrounding Markdown code fence if the model adds one.
    if content.startswith("```"):
        lines = content.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        content = "\n".join(lines).strip()

    try:
        result = json.loads(content)

    except json.JSONDecodeError:
        # Tolerate explanatory text before or after a JSON object.
        start = content.find("{")
        end = content.rfind("}")

        if start == -1 or end <= start:
            raise ValueError(
                "The local LLM did not return a valid JSON object. "
                f"Response received: {content[:300]}"
            )

        try:
            result = json.loads(content[start:end + 1])

        except json.JSONDecodeError as error:
            raise ValueError(
                "The local LLM returned invalid classification JSON. "
                f"Response received: {content[:300]}"
            ) from error

    if not isinstance(result, dict):
        raise ValueError(
            "The classification result must be a JSON object."
        )

    return result


def classify_email(subject, body):
    subject = str(subject or "").strip()
    body = str(body or "").strip()

    # Prevent very large emails from consuming excessive context.
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS] + "\n[Email body truncated]"

    user_prompt = f"""
Classify this email using the system instructions.

Subject:
{subject or "(No Subject)"}

Body:
{body or "(No email body available)"}

Return only one JSON object with exactly these keys:
"category" and "reason".

Example format:
{{
  "category": "Transactional",
  "reason": "The email confirms or documents a transaction or service activity."
}}
"""

    content = _request_model(user_prompt)

    if not content:
        raise ValueError(
            "The local LLM returned an empty classification response."
        )

    result = _parse_json_result(content)

    category = result.get("category")
    reason = result.get("reason")

    if not isinstance(category, str):
        raise ValueError(
            "Classification is missing a valid category."
        )

    # Normalize category case and whitespace.
    category_lookup = {
        name.lower(): name
        for name in ALLOWED_CATEGORIES
    }

    category = category_lookup.get(category.strip().lower())

    if category is None:
        raise ValueError(
            "Invalid category returned by the model: "
            f"{result.get('category')}"
        )

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError(
            "Classification is missing a useful reason."
        )

    return {
        "category": category,
        "reason": reason.strip()
    }


if __name__ == "__main__":
    print("=== AI Email Classifier ===\n")

    subject = input("Email subject:\n> ")
    body = input("\nEmail body:\n> ")

    print("\nClassifying email...")

    try:
        result = classify_email(subject, body)

        print("\n" + "=" * 50)
        print("CLASSIFICATION")
        print("=" * 50)
        print(f"\nCategory: {result['category']}")
        print(f"Reason: {result['reason']}")

    except requests.exceptions.Timeout:
        print(
            "\nClassification failed: LM Studio did not respond "
            f"within {REQUEST_TIMEOUT} seconds. Check that the "
            "model is loaded and the local server is running."
        )

    except requests.exceptions.RequestException as error:
        print(
            "\nClassification failed because of an API request error:"
            f"\n{error}"
        )

    except Exception as error:
        print(f"\nClassification failed: {error}")