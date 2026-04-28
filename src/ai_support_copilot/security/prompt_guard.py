import re

PROMPT_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"ignore (all )?(previous|prior) instructions",
        r"reveal (the )?(system|developer) prompt",
        r"print (the )?(hidden|system) instructions",
        r"you are now",
    ]
]


def has_prompt_injection(text: str) -> bool:
    return any(pattern.search(text) for pattern in PROMPT_INJECTION_PATTERNS)


def neutralize_context(text: str) -> str:
    return text.replace("```", "'''").replace("<system>", "").replace("</system>", "")
