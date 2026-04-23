import hashlib
import re


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text.split()) * 1.3))


def sanitize_user_text(text: str, *, max_length: int = 4000) -> str:
    cleaned = text.replace("\x00", "").strip()
    return cleaned[:max_length]
