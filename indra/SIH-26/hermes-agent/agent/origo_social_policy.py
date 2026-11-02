"""Conservative per-request social policy; never mutates cached schemas or history."""
import re

_SOCIAL = re.compile(
    r"(?:hi|hey|hello|hello there|hey there|good morning|good afternoon|good evening|"
    r"good night|thanks|thank you|thanks a lot|thank you very much|bye|goodbye)"
    r"[\s!.,?]*(?:👋|😊|🙏)?[\s!.,?]*", re.IGNORECASE,
)


def is_social_turn(messages: list) -> bool:
    if not messages or not isinstance(messages[-1], dict):
        return False
    message = messages[-1]
    if message.get("role") != "user":
        return False
    content = message.get("content")
    if isinstance(content, list):
        if len(content) != 1 or not isinstance(content[0], dict) or content[0].get("type") != "text":
            return False
        content = content[0].get("text")
    return isinstance(content, str) and len(content) <= 80 and bool(_SOCIAL.fullmatch(content.strip()))


def apply_social_policy(payload: dict, messages: list, *, enabled: bool) -> dict:
    if not enabled or not payload.get("tools") or not is_social_turn(messages):
        return payload
    return {**payload, "tool_choice": "none"}
