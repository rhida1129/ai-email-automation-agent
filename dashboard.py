import streamlit as st

from email_cache import (
    initialize_database,
    get_all_emails,
    get_email_count,
    get_uncategorized_emails,
    update_email_category,
)

from gmail_reader import sync_inbox
from email_classifier import classify_email
from email_responder import generate_response
from send_email import send_email


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AI Email Automation Agent",
    page_icon="📧",
    layout="wide",
)


# ============================================================
# INITIALIZE DATABASE
# ============================================================

initialize_database()


# ============================================================
# CONSTANTS AND HELPERS
# ============================================================

VALID_CATEGORIES = [
    "Work",
    "Personal",
    "Promotional",
    "Transactional",
    "Urgent",
]

FILTER_OPTIONS = [
    "All",
    "Work",
    "Personal",
    "Promotional",
    "Transactional",
    "Urgent",
]


def normalize_category(value):
    """Normalize category values to prevent case/space mismatches."""
    if value is None:
        return ""

    return str(value).strip().casefold()


def clear_ai_response_state():
    """Clear response-related state when another email is opened."""
    for key in (
        "ai_response",
        "edited_response",
        "response_editor",
    ):
        st.session_state.pop(key, None)


def classify_uncategorized_emails(batch_size=10):
    """Classify a batch of uncategorized cached emails."""

    uncategorized_emails = get_uncategorized_emails()

    if not uncategorized_emails:
        st.info("All cached emails are already classified.")
        return

    emails_to_classify = uncategorized_emails[:batch_size]

    st.info(
        f"🤖 Classifying {len(emails_to_classify)} "
        "uncategorized email(s) with Qwen 3.5 9B..."
    )

    progress_bar = st.progress(0)
    status_text = st.empty()

    successful = 0
    failed = 0
    total_to_classify = len(emails_to_classify)

    for index, email in enumerate(emails_to_classify, start=1):
        subject = email.get("subject") or "(No Subject)"

        status_text.write(
            f"Classifying {index}/{total_to_classify}: {subject}"
        )

        try:
            classification = classify_email(
                email.get("subject", ""),
                email.get("body", ""),
            )

            category_result = classification.get("category")
            reason = classification.get("reason", "")

            # Match the AI result against the approved category names.
            matched_category = next(
                (
                    valid_category
                    for valid_category in VALID_CATEGORIES
                    if normalize_category(valid_category)
                    == normalize_category(category_result)
                ),
                None,
            )

            if matched_category is None:
                raise ValueError(
                    f"Invalid category returned by AI: "
                    f"{category_result}"
                )

            update_email_category(
                email["message_id"],
                matched_category,
                reason,
            )

            successful += 1

        except Exception as error:
            failed += 1

            st.error(
                f"Failed to classify '{subject}': {error}"
            )

        progress_bar.progress(index / total_to_classify)

    progress_bar.empty()
    status_text.empty()

    if failed == 0:
        st.success(
            f"Classification completed successfully. "
            f"{successful} email(s) classified."
        )
    else:
        st.warning(
            f"Classification batch completed. "
            f"Successful: {successful} | Failed: {failed}"
        )

    # Reload the page so the latest categories and counts appear.
    st.rerun()


# ============================================================
# PAGE HEADER
# ============================================================

st.title("📧 AI Email Automation Agent")

st.caption(
    "AI-powered Gmail management with human-in-the-loop review"
)

st.divider()


# ============================================================
# SIDEBAR: CATEGORY FILTER
# ============================================================

st.sidebar.title("📂 Categories")

category = st.sidebar.radio(
    "Filter emails",
    FILTER_OPTIONS,
    key="email_category_filter",
)


# ============================================================
# SIDEBAR: GMAIL SYNC
# ============================================================

st.sidebar.divider()
st.sidebar.subheader("📥 Gmail Sync")

total_emails = get_email_count()

st.sidebar.metric(
    "Cached Emails",
    total_emails,
)

if st.sidebar.button("🔄 Refresh / Sync Gmail"):
    with st.spinner("Checking Gmail for new emails..."):
        try:
            new_emails = sync_inbox(batch_size=100)

            if new_emails:
                st.success(
                    f"Added {len(new_emails)} new email(s) to the cache."
                )
            else:
                st.info("No new Gmail emails found.")

            st.rerun()

        except Exception as error:
            st.error(f"Gmail sync failed: {error}")


# ============================================================
# SIDEBAR: AI CLASSIFICATION
# ============================================================

st.sidebar.divider()

uncategorized_emails = get_uncategorized_emails()
uncategorized_count = len(uncategorized_emails)

st.sidebar.subheader("🤖 AI Classification")

if uncategorized_count > 0:
    st.sidebar.write(
        f"{uncategorized_count} email(s) need classification."
    )

    classify_count = min(10, uncategorized_count)

    if st.sidebar.button(
        f"🤖 Classify Next {classify_count}",
        type="primary",
    ):
        classify_uncategorized_emails(batch_size=10)
else:
    st.sidebar.success("All cached emails are classified.")


# ============================================================
# LOAD EMAILS
# ============================================================

emails = get_all_emails()


# ============================================================
# CATEGORY COUNTS
# ============================================================

category_counts = {
    category_name: 0
    for category_name in VALID_CATEGORIES
}

uncategorized_count = 0

for email in emails:
    email_category = normalize_category(email.get("category"))

    matched_category = next(
        (
            category_name
            for category_name in VALID_CATEGORIES
            if normalize_category(category_name) == email_category
        ),
        None,
    )

    if matched_category:
        category_counts[matched_category] += 1
    else:
        uncategorized_count += 1


st.sidebar.divider()

st.sidebar.write(
    f"💼 Work: {category_counts['Work']}"
)

st.sidebar.write(
    f"👤 Personal: {category_counts['Personal']}"
)

st.sidebar.write(
    f"🚨 Urgent: {category_counts['Urgent']}"
)

st.sidebar.write(
    f"📢 Promotional: {category_counts['Promotional']}"
)

st.sidebar.write(
    f"🧾 Transactional: {category_counts['Transactional']}"
)

if uncategorized_count > 0:
    st.sidebar.write(
        f"❓ Uncategorized: {uncategorized_count}"
    )


# ============================================================
# EMAIL FILTERING — FIXED
# ============================================================

if category == "All":
    filtered_emails = emails.copy()
else:
    selected_category = normalize_category(category)

    filtered_emails = [
        email
        for email in emails
        if normalize_category(email.get("category"))
        == selected_category
    ]


# ============================================================
# MAIN LAYOUT
# ============================================================

email_column, detail_column = st.columns([1, 1])


# ============================================================
# EMAIL LIST
# ============================================================

with email_column:
    st.subheader("📨 Inbox")

    st.write(
        f"{len(filtered_emails)} email(s) found in "
        f"'{category}'"
    )

    if not filtered_emails:
        st.info(
            f"No emails found in the '{category}' category."
        )

    else:
        for email in filtered_emails:
            subject = email.get("subject") or "(No Subject)"
            sender = email.get("sender") or "Unknown sender"
            email_category = email.get("category") or "Uncategorized"
            message_id = email.get("message_id")

            with st.container(border=True):
                st.markdown(f"### {subject}")

                st.write(f"From: {sender}")

                st.caption(f"Category: {email_category}")

                if st.button(
                    "Open",
                    key=f"open_{message_id}",
                ):
                    # Store the ID instead of a potentially stale
                    # copy of the email record.
                    st.session_state["selected_email_id"] = message_id

                    clear_ai_response_state()

                    st.rerun()


# ============================================================
# EMAIL DETAILS
# ============================================================

with detail_column:
    st.subheader("📄 Email Details")

    selected_email_id = st.session_state.get(
        "selected_email_id"
    )

    selected_email = next(
        (
            email
            for email in emails
            if email.get("message_id") == selected_email_id
        ),
        None,
    )

    if selected_email:
        subject = selected_email.get("subject") or "(No Subject)"
        sender = selected_email.get("sender") or "Unknown sender"
        body = selected_email.get("body") or ""
        email_category = (
            selected_email.get("category") or "Uncategorized"
        )

        st.markdown(f"### {subject}")

        st.write(f"**From:** {sender}")

        st.write(f"**Category:** {email_category}")

        st.divider()

        st.write(body)

        st.divider()

        # ====================================================
        # AI RESPONSE
        # ====================================================

        st.subheader("🤖 AI Response")

        if "ai_response" not in st.session_state:
            st.write(
                "Generate an AI-powered response to this email."
            )

            if st.button(
                "✨ Generate AI Response",
                type="primary",
            ):
                with st.spinner(
                    "Generating response with Qwen 3.5 9B..."
                ):
                    try:
                        response = generate_response(
                            subject,
                            body,
                        )

                        st.session_state["ai_response"] = response

                        st.rerun()

                    except Exception as error:
                        st.error(
                            f"Failed to generate response: {error}"
                        )

        else:
            ai_response = st.session_state["ai_response"]

            response_body = st.session_state.get(
                "edited_response",
                ai_response["body"],
            )

            st.markdown(
                f"**Subject:** {ai_response['subject']}"
            )

            edited_body = st.text_area(
                "Response",
                value=response_body,
                height=250,
                key="response_editor",
            )

            st.session_state["edited_response"] = edited_body

            st.caption(
                "You can edit the AI-generated response "
                "before sending."
            )

            col1, col2 = st.columns(2)

            with col1:
                if st.button("💾 Save Edited Response"):
                    st.session_state["edited_response"] = edited_body

                    st.success("Edited response saved.")

            with col2:
                if st.button("🔄 Regenerate Response"):
                    with st.spinner(
                        "Generating a new response..."
                    ):
                        try:
                            response = generate_response(
                                subject,
                                body,
                            )

                            st.session_state["ai_response"] = response

                            st.session_state.pop(
                                "edited_response",
                                None,
                            )

                            st.session_state.pop(
                                "response_editor",
                                None,
                            )

                            st.rerun()

                        except Exception as error:
                            st.error(
                                "Failed to regenerate response: "
                                f"{error}"
                            )

            st.divider()

            # =================================================
            # SEND RESPONSE
            # =================================================

            st.subheader("📤 Send Response")

            st.warning(
                "Review the response carefully before sending."
            )

            if st.button(
                "📤 Send Response",
                type="primary",
            ):
                final_body = st.session_state.get(
                    "edited_response",
                    ai_response["body"],
                )

                try:
                    with st.spinner(
                        "Sending email through Gmail..."
                    ):
                        send_email(
                            sender,
                            ai_response["subject"],
                            final_body,
                        )

                    st.success(
                        f"Response sent successfully to {sender}."
                    )

                except Exception as error:
                    st.error(
                        f"Failed to send email: {error}"
                    )

    else:
        st.info(
            "Select an email from the inbox to view its details."
        )