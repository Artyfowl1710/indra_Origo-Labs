"""Truthful capability inventory: distinguish implemented pathways from unprobed model claims."""
from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlsplit


def endpoint_is_loopback(url: str) -> bool:
    try:
        host = (urlsplit(url).hostname or "").lower()
        if host == "localhost":
            return True
        return ipaddress.ip_address(host).is_loopback
    except (ValueError, TypeError):
        return False


def capability_snapshot(provider) -> dict:
    """Return implementation-level and inference-level capabilities separately."""
    endpoint = str(getattr(provider, "base_url", ""))
    is_local = endpoint_is_loopback(endpoint)
    return {
        "schema_version": 1,
        "provider": {
            "protocol": "OpenAI-compatible HTTP",
            "endpoint": getattr(provider, "display_endpoint", "configured endpoint"),
            "local_endpoint": is_local,
            "routing": "Configured endpoint; route/model selection is owned by the configured gateway.",
        },
        "transport": {
            "chat_completions": "implemented",
            "streaming": "implemented_with_fallback",
            "tool_calls": "implemented_in_client; upstream_support_not_probed",
        },
        "modalities": {
            "text_input": {"status": "implemented"},
            "text_output": {"status": "implemented"},
            "image_input": {
                "status": "pass_through_available_not_probed",
                "note": "Images are only forwarded when attached by the user. Actual support depends on the selected model and gateway.",
            },
            "pdf_input": {"status": "opt_in_only" if os.getenv("INDRA_ALLOW_UNSANDBOXED_PDF", "false").strip().lower() in {"1", "true", "yes", "on"} else "disabled_by_default_security_gate", "ocr": "not_implemented", "note": "pypdf parsing is in-process; only enable for trusted PDFs until upstream resource-exhaustion advisories are addressed."},
            "voice_input": {
                "status": "browser_api_dependent",
                "api": "Web Speech API / SpeechRecognition",
                "note": "Recognition may use browser-vendor services; it is not guaranteed to run fully locally.",
            },
            "voice_output": {"status": "browser_api_dependent", "api": "SpeechSynthesis"},
            "audio_file_understanding": {"status": "preview_only_not_sent_to_model"},
            "video_file_understanding": {"status": "preview_only_not_sent_to_model"},
        },
        "limits": {"max_attachments": 4, "max_file_bytes": 5 * 1024 * 1024,
                   "max_total_binary_bytes": 6 * 1024 * 1024, "max_pdf_pages": 40},
        "provider_claims": "No model-specific vision/audio/tool-call capability is marked verified until an explicit probe is run.",
    }
