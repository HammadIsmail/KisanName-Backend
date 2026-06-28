import unicodedata


def is_rtl_text(text: str) -> bool:
    """Check if text contains predominantly RTL (Arabic/Urdu) characters."""
    rtl_count = sum(
        1 for c in text if unicodedata.bidirectional(c) in ("R", "AL", "AN")
    )
    return rtl_count > len(text) * 0.3


def clean_urdu_text(text: str) -> str:
    """Strip leading/trailing whitespace and normalize unicode for Urdu text."""
    return text.strip()


def truncate_urdu(text: str, max_chars: int = 1000) -> str:
    """Truncate text at word boundary to avoid cutting mid-word."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    return truncated[:last_space] if last_space > 0 else truncated
