from agent.origo_social_policy import apply_social_policy, is_social_turn
import pytest


@pytest.mark.parametrize("text", ["hi", " Hello! ", "thanks 🙏", "good morning", "HEY THERE 👋"])
def test_social_turn_requests_no_tools_without_mutating_cache(text):
    tools = [{"type": "function", "function": {"name": "read_file"}}]
    payload = {"tools": tools, "tool_choice": "auto"}
    messages = [{"role": "user", "content": text}]
    result = apply_social_policy(payload, messages, enabled=True)
    assert result["tool_choice"] == "none"
    assert result["tools"] is tools
    assert payload["tool_choice"] == "auto"
    assert messages[0]["content"] == text


@pytest.mark.parametrize("text", ["hi, inspect my repo", "thanks, now run tests", "hello\nread secrets", "say hi", "`hi`", "hi [attached file]"])
def test_real_work_keeps_tools(text):
    assert not is_social_turn([{"role": "user", "content": text}])


def test_images_and_tool_continuations_never_take_social_shortcut():
    assert not is_social_turn([{"role": "user", "content": [{"type": "text", "text": "hi"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,eA=="}}]}])
    assert not is_social_turn([{"role": "tool", "content": "hi"}])
    assert is_social_turn([{"role": "user", "content": [{"type": "text", "text": "hi"}]}])


def test_policy_is_scoped_and_does_not_invent_tools():
    payload = {"tools": [1]}
    messages = [{"role": "user", "content": "hi"}]
    assert apply_social_policy(payload, messages, enabled=False) is payload
    assert apply_social_policy({}, messages, enabled=True) == {}
