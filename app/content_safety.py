"""Bounded offline heuristics for untrusted document text.

This is a conservative quarantine filter, not a learned classifier or a complete
prompt-injection defence. Decisions contain rule IDs, never source text.
"""
import re
import unicodedata

SCANNER_VERSION = 2
MAX_SCAN_CHARS = 2_000_000
_RULES = {
    "instruction_override": r"\b(?:ignore|disregard|forget)\s+(?:(?:all|any|the|your|these)\s+){0,3}(?:previous|prior|above|system|developer|safety)\s+(?:instructions?|prompts?|rules?|messages?|polic(?:y|ies))\b",
    "role_spoofing": r"(?:<\|(?:im_start|start_header_id)\|>\s*(?:system|developer)|\[\s*INST\s*\]\s*<<SYS>>|^\s*\[(?:system|developer)\]\s*:?)",
    "evidence_escape": r"</\s*(?:document_evidence|tool_evidence|untrusted_content)\s*>",
    "secret_exfiltration": r"\b(?:send|upload|post|transmit|exfiltrate|forward)\b[^\n.]{0,180}\b(?:api[ _-]?keys?|credentials?|passwords?|private[ _-]?keys?|access[ _-]?tokens?|\.env)\b",
    "approval_bypass": r"\b(?:bypass|disable|skip)\b[^\n.]{0,65}\b(?:human\s+)?(?:approvals?|safety\s+(?:checks?|guards?)|permission\s+checks?)\b",
}
_COMPILED = {name: re.compile(pattern, re.IGNORECASE | re.MULTILINE) for name, pattern in _RULES.items()}


def scan_document(text):
    if not isinstance(text, str):
        raise TypeError("Document text must be a string")
    if len(text) > MAX_SCAN_CHARS:
        return {"version": SCANNER_VERSION, "quarantined": True, "rules": ["scan_limit"]}
    # Strip zero-width/control formatting, then collapse whitespace. Preserve
    # newlines for bounded line patterns and role headers.
    normalized = unicodedata.normalize("NFKC", text)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Cf")
    normalized = re.sub(r"[^\S\n]+", " ", normalized)
    rules = [name for name, pattern in _COMPILED.items() if pattern.search(normalized)]
    return {"version": SCANNER_VERSION, "quarantined": bool(rules), "rules": rules}
