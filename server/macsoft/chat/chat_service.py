from __future__ import annotations


def build_mock_assistant_reply(user_message: str) -> str:
    clean_message = (user_message or "").strip()

    if not clean_message:
        return "Hello from MacSoft Server. Your message was empty."

    return (
        "Hello from MacSoft Server. "
        "Stage 3 chat stream is working. "
        f"You said: {clean_message}"
    )
