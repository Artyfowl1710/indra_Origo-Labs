"""Reusable OpenAI-compatible HTTP client with discovery, SSE decoding, and safe errors."""
from __future__ import annotations

import json
import os
import time
from urllib.parse import urlsplit, urlunsplit

import httpx


class ProviderError(RuntimeError):
    """An actionable provider/configuration failure safe to display in the UI."""


def _env_float(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    if value != value or value in (float("inf"), float("-inf")):
        value = default
    return max(low, min(high, value))


def safe_endpoint_label(url: str) -> str:
    """Expose only conventional API path segments; redact arbitrary path tokens as well as URL secrets."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or "configured endpoint"
        if parts.port:
            host += f":{parts.port}"
        known_segments = {"v1", "v2", "api", "openai", "chat", "completions", "models", "embeddings",
                          "responses", "audio", "images", "inference", "serving", "predict"}
        safe_segments = []
        for segment in [part for part in parts.path.split("/") if part]:
            if segment.lower() in known_segments:
                safe_segments.append(segment)
            else:
                safe_segments.append("[redacted]")
        path = "/" + "/".join(safe_segments) if safe_segments else ""
        return urlunsplit((parts.scheme, host, path, "", ""))
    except (ValueError, TypeError):
        return "configured endpoint"


class OpenAICompatibleProvider:
    def __init__(self):
        self.profile = "local"
        self.base_url = ""
        self.api_key = "local"
        self.model = "auto"
        self._resolved_model: str | None = None
        self._models_checked_at = 0.0
        timeout = _env_float("INDRA_REQUEST_TIMEOUT", 120, 5, 900)
        connect_timeout = _env_float("INDRA_CONNECT_TIMEOUT", 3, 0.2, 30)
        self._timeout = httpx.Timeout(timeout, connect=connect_timeout)
        self._client = self._new_client()
        self.use_profile("local")

    def profile_info(self) -> dict:
        hosted_url = os.getenv("INDRA_HOSTED_BASE_URL", "").strip().rstrip("/")
        hosted_key = os.getenv("INDRA_HOSTED_API_KEY", "").strip()
        return {
            "active": self.profile,
            "profiles": [
                {"id": "local", "label": "Local gateway", "configured": True,
                 "endpoint": safe_endpoint_label(os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8100/v1").strip() or "http://127.0.0.1:8100/v1"),
                 "api_key_configured": bool(os.getenv("OPENAI_API_KEY", "local").strip())},
                {"id": "hosted", "label": "Hosted OpenAI-compatible endpoint", "configured": bool(hosted_url and hosted_key),
                 "endpoint": safe_endpoint_label(hosted_url) if hosted_url else "not configured",
                 "api_key_configured": bool(hosted_key)},
            ],
            "note": "Only profile IDs and redacted endpoints are returned. API keys are never returned.",
        }

    def use_profile(self, profile: str) -> None:
        if profile == "local":
            base_url = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8100/v1").strip().rstrip("/") or "http://127.0.0.1:8100/v1"
            api_key = os.getenv("OPENAI_API_KEY", "local").strip() or "local"
            model = os.getenv("MODEL", "auto").strip() or "auto"
        elif profile == "hosted":
            base_url = os.getenv("INDRA_HOSTED_BASE_URL", "").strip().rstrip("/")
            api_key = os.getenv("INDRA_HOSTED_API_KEY", "").strip()
            model = os.getenv("INDRA_HOSTED_MODEL", "auto").strip() or "auto"
            if not base_url or not api_key:
                raise ProviderError("Hosted profile is not configured. Set INDRA_HOSTED_BASE_URL and INDRA_HOSTED_API_KEY in .env, then restart Origo.")
            try:
                parts = urlsplit(base_url)
                if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
                    raise ValueError
            except ValueError as exc:
                raise ProviderError("Hosted profile requires a clean HTTPS base URL without embedded credentials, query, or fragment.") from exc
        else:
            raise ProviderError("Unknown provider profile. Choose local or hosted.")
        if not base_url:
            raise ProviderError("The selected provider profile has no base URL configured.")
        self.profile, self.base_url, self.api_key, self.model = profile, base_url, api_key, model
        self._resolved_model = None
        self._models_checked_at = 0.0

    def _new_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout,
            limits=httpx.Limits(max_connections=12, max_keepalive_connections=6, keepalive_expiry=30),
            follow_redirects=False,
        )

    def _get_client(self) -> httpx.AsyncClient:
        # Test clients and application restarts may close the previous lifespan's client.
        if self._client.is_closed:
            self._client = self._new_client()
        return self._client

    @property
    def display_endpoint(self) -> str:
        return safe_endpoint_label(self.base_url)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_models(self, force: bool = False) -> list[str]:
        now = time.monotonic()
        if not force and self._resolved_model and now - self._models_checked_at < 30:
            return [self._resolved_model]
        try:
            response = await self._get_client().get(self.base_url + "/models", headers=self._headers(), timeout=httpx.Timeout(4, connect=1.5))
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ProviderError("The model gateway returned an invalid /models response. Expected a JSON object.")
            rows = payload.get("data", [])
            if not isinstance(rows, list):
                rows = []
            models = [str(item.get("id")) for item in rows if isinstance(item, dict) and item.get("id")]
            self._models_checked_at = now
            if not models:
                raise ProviderError("The model gateway answered /models but advertised no model IDs. Check its model aliases and startup logs.")
            auto_detect = os.getenv("INDRA_AUTO_DETECT_MODEL", "true").strip().lower() in {"1", "true", "yes", "on"}
            if self.model == "auto" or (auto_detect and self.model not in models):
                self._resolved_model = models[0]
            else:
                self._resolved_model = self.model
            return models
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ProviderError(
                f"Cannot reach the model gateway at {self.display_endpoint}. Start llama-swap/llama.cpp or check Settings → Diagnostics ({type(exc).__name__})."
            ) from exc

    def _headers(self, streaming: bool = False) -> dict[str, str]:
        headers = {"Authorization": "Bearer " + self.api_key, "Accept": "text/event-stream" if streaming else "application/json"}
        return headers

    def _choose_message(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ProviderError("The model gateway returned a non-object JSON response.")
        choices = payload.get("choices") or []
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderError("The model gateway returned no chat completion choices. Check server logs and the selected model's chat template.")
        msg = choices[0].get("message")
        if not isinstance(msg, dict):
            raise ProviderError("The model gateway returned an invalid assistant message.")
        content = msg.get("content")
        if isinstance(content, list):
            # Compatible multimodal endpoints may return text blocks. Preserve readable text and omit non-text payloads.
            text_parts = []
            for part in content[:128]:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    text_parts.append(part["text"][:20000])
            msg["content"] = "\n".join(text_parts)
        elif not isinstance(content, (str, type(None))):
            msg["content"] = ""
        msg.setdefault("role", "assistant")
        return msg

    async def chat(self, messages: list[dict], tools: list[dict] | None = None, max_tokens: int | None = None) -> dict:
        model_ids = await self.list_models()
        model = self._resolved_model or (model_ids[0] if model_ids else self.model)
        payload = {"model": model, "messages": messages, "temperature": 0.2, "stream": False}
        if tools:
            payload.update(tools=tools, tool_choice="auto")
        if max_tokens is not None:
            payload["max_tokens"] = max(1, min(int(max_tokens), 256))
        try:
            response = await self._get_client().post(self.base_url + "/chat/completions", json=payload, headers=self._headers())
            if response.status_code in (400, 404) and "model" in response.text.lower():
                self._resolved_model = None
                models = await self.list_models(force=True)
                payload["model"] = self._resolved_model or models[0]
                response = await self._get_client().post(self.base_url + "/chat/completions", json=payload, headers=self._headers())
            if response.status_code >= 400:
                # Do not pass full upstream body into the UI; it might contain internal paths or credentials.
                raise ProviderError(f"Model gateway returned HTTP {response.status_code} at {self.display_endpoint}. Check Diagnostics and the model-server log.")
            return self._choose_message(response.json())
        except ProviderError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            raise ProviderError(f"Model request failed at {self.display_endpoint} ({type(exc).__name__}). Check Diagnostics and the model-server log.") from exc

    async def chat_stream(self, messages: list[dict], tools: list[dict] | None = None, on_token=None) -> dict:
        """Stream SSE deltas while reconstructing a complete tool-call message."""
        model_ids = await self.list_models()
        model = self._resolved_model or (model_ids[0] if model_ids else self.model)
        payload = {"model": model, "messages": messages, "temperature": 0.2, "stream": True}
        if tools:
            payload.update(tools=tools, tool_choice="auto")
        content_parts: list[str] = []
        calls: dict[int, dict] = {}
        try:
            async with self._get_client().stream("POST", self.base_url + "/chat/completions", json=payload,
                                           headers=self._headers(streaming=True)) as response:
                if response.status_code >= 400:
                    if response.status_code in (400, 404, 405, 415, 501):
                        # These status codes commonly indicate unsupported SSE/stream options on compatible servers.
                        fallback = await self.chat(messages, tools)
                        content = fallback.get("content")
                        if isinstance(content, str) and content and on_token:
                            on_token(content)
                        return fallback
                    raise ProviderError(f"Streaming request returned HTTP {response.status_code} at {self.display_endpoint}. Check Diagnostics.")
                content_type = response.headers.get("content-type", "").lower()
                if "text/event-stream" not in content_type:
                    try:
                        packet = json.loads((await response.aread()).decode("utf-8", "replace"))
                        msg = self._choose_message(packet)
                    except (ValueError, KeyError, TypeError):
                        raise ProviderError("The endpoint did not return a valid SSE stream or chat completion response.")
                    content = msg.get("content")
                    if isinstance(content, str) and content and on_token:
                        on_token(content)
                    return msg
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        packet = json.loads(data)
                    except ValueError:
                        continue
                    if not isinstance(packet, dict):
                        continue
                    choices = packet.get("choices") or []
                    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                        continue
                    delta = choices[0].get("delta") or {}
                    if not isinstance(delta, dict):
                        continue
                    token = delta.get("content")
                    if isinstance(token, str) and token:
                        content_parts.append(token)
                        if on_token:
                            on_token(token)
                    for tc in delta.get("tool_calls") or []:
                        if not isinstance(tc, dict):
                            continue
                        idx = tc.get("index", 0)
                        if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0 or idx > 64:
                            continue
                        row = calls.setdefault(idx, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                        if tc.get("id"):
                            row["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if not isinstance(fn, dict):
                            continue
                        if fn.get("name"):
                            row["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            row["function"]["arguments"] += fn["arguments"]
            msg = {"role": "assistant", "content": "".join(content_parts)}
            if calls:
                msg["tool_calls"] = [calls[k] for k in sorted(calls)]
            elif not content_parts:
                # Some compatible servers close an SSE stream without emitting a final choice.
                return await self.chat(messages, tools)
            return msg
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ProviderError(f"Streaming model request failed at {self.display_endpoint} ({type(exc).__name__}). Check Diagnostics.") from exc
