def generate_chat_title(first_user_message: str) -> str:
    clean_text = " ".join((first_user_message or "").split()).strip()
    if not clean_text:
        return "New Chat"

    words = clean_text.split()
    title = " ".join(words[:6]).strip()
    return title[:60].rstrip(".,:;!?") or "New Chat"

