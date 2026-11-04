import re
from dataclasses import dataclass

DEMO_USERS = {
    "admin": {"role": "Administrator", "label": "Demo Administrator"},
    "kb_manager": {"role": "Knowledge Base Manager", "label": "Demo Knowledge Manager"},
    "support": {"role": "Support Agent", "label": "Demo Support Agent"},
    "standard": {"role": "Standard User", "label": "Demo Standard User"},
}
ROLE_ACCESS = {
    "Administrator": {"Public", "Internal", "Confidential"},
    "Knowledge Base Manager": {"Public", "Internal"},
    "Support Agent": {"Public", "Internal"},
    "Standard User": {"Public"},
}
SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_ -]?key|access[_ -]?token|secret[_ -]?key|password)\s*[:=]\s*[^\s,;]{8,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
]
PII_PATTERNS = [
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[REDACTED_EMAIL]"),
    (re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\d{10})\b"), "[REDACTED_PHONE]"),
]
@dataclass(frozen=True)
class UserContext:
    user_id: str
    role: str

def resolve_demo_user(user_id: str | None) -> UserContext | None:
    if not user_id or user_id not in DEMO_USERS:
        return None
    return UserContext(user_id=user_id, role=DEMO_USERS[user_id]["role"])

def allowed_classifications(role: str) -> set[str]:
    return ROLE_ACCESS.get(role, set())

def contains_high_risk_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)

def redact_sensitive(text: str) -> str:
    redacted = text
    for pattern, replacement in PII_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted
