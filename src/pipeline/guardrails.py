import re


INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior) instructions",
    r"reveal (your|the) (system prompt|instructions)",
    r"show (me )?(your|the) system prompt",
    r"(reveal|show|print).*(system prompt|internal instructions|hidden instructions|api key)",
    r"developer message",
    r"jailbreak",
    r"act as (an? )?(administrator|developer|system)",
]


def detect_prompt_injection(text: str) -> bool:
    normalized = text.lower()

    return any(
        re.search(pattern, normalized)
        for pattern in INJECTION_PATTERNS
    )


def validate_output(text: str) -> None:
    suspicious_terms = (
        "api key",
        "system prompt",
        "developer message",
    )

    if any(
        term in text.lower()
        for term in suspicious_terms
    ):
        raise ValueError(
            "Output blocked by security guardrail"
        )