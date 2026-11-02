"""Per-action approval broker for network, Docker sandbox and plugin calls.

The broker never performs the operation itself. It pauses the agent loop until the local UI
answers, then returns a one-shot decision. A narrowly scoped host grant is held in memory only.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
import threading
from urllib.parse import urlsplit
from typing import Any, Callable

NETWORK_TOOLS = {"web_search", "web_fetch", "web_research", "web_crawl"}
APPROVAL_TIMEOUT_SECONDS = 180
MAX_PENDING_PERMISSIONS = 16


def _display_url(value: str) -> tuple[str | None, str]:
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").encode("idna").decode("ascii").lower().rstrip(".") or None
        if not host:
            return None, "Target URL could not be parsed."
        path = parts.path or "/"
        # Query strings and fragments can contain access tokens; never echo them in approval UI/logs.
        display = f"{parts.scheme}://{host}{path[:500]}"
        return host, display
    except (ValueError, UnicodeError):
        return None, "Target URL could not be parsed."


def _resolve_false_if_pending(future: asyncio.Future) -> None:
    """Run only on the future's event loop; thread-safe permission revocation helper."""
    if not future.done():
        future.set_result(False)


class PermissionBroker:
    def __init__(self, network_policy: str = "ask"):
        self.network_policy = network_policy if network_policy in {"ask", "deny"} else "ask"
        self._pending: dict[str, dict[str, Any]] = {}
        self._session_domains: set[str] = set()
        # API diagnostics run in worker threads while the agent pauses on its ASGI loop.
        # Guard shared maps/settings without holding the lock while awaiting user approval.
        self._lock = threading.RLock()

    def set_network_policy(self, value: str) -> str:
        if value not in {"ask", "deny"}:
            raise ValueError("network policy must be 'ask' or 'deny'")
        with self._lock:
            self.network_policy = value
            if value == "deny":
                # Revoking permission also rejects network actions that are currently waiting
                # in the approval queue. Resolve futures on their owning asyncio loop.
                for row in self._pending.values():
                    public = row["public"]
                    future = row["future"]
                    if public.get("tool") in NETWORK_TOOLS:
                        row["loop"].call_soon_threadsafe(_resolve_false_if_pending, future)
        return value

    def clear_session_grants(self) -> None:
        with self._lock:
            self._session_domains.clear()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"network_policy": self.network_policy, "session_allowed_domains": sorted(self._session_domains),
                    "pending_count": len(self._pending), "approval_timeout_seconds": APPROVAL_TIMEOUT_SECONDS}

    def pending(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{**row["public"], "scope_options": list(row["public"].get("scope_options", []))}
                    for row in self._pending.values()]

    def _build_request(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        host: str | None = None
        kind = "plugin" if tool.startswith("plugin__") else "sandbox" if tool == "sandbox_run" else "network"
        title = "External network access requested"
        summary = "The agent wants to access the public web."
        detail = "Approve only if this query or source is appropriate to send outside your machine."
        scope_options = ["once"]
        if tool == "web_search":
            query = str(args.get("query", ""))[:1000]
            try:
                from .tools import redact_sensitive_text
                query = redact_sensitive_text(query)
            except Exception:
                pass
            summary = "Search public web results"
            detail = "Search query sent to the configured public search provider:\n\n" + query
        elif tool == "web_research":
            query = str(args.get("query", ""))[:1000]
            try:
                from .tools import redact_sensitive_text
                query = redact_sensitive_text(query)
            except Exception:
                pass
            summary = "Search the public web, then fetch source pages"
            detail = f"Query sent to the public search provider:\n\n{query}\n\nMay fetch up to {min(4, max(1, int(args.get('max_pages', 3) or 3)))} public source pages. Each URL is checked independently."
        elif tool in {"web_fetch", "web_crawl"}:
            host, safe_url = _display_url(str(args.get("url", "")))
            summary = ("Fetch one public page" if tool == "web_fetch" else "Crawl pages on one public host")
            detail = f"Target: {safe_url}\nHost: {host or 'unresolved'}\nNetwork request starts only after approval. Query strings are hidden in this preview."
            if tool == "web_crawl":
                detail += f"\nMaximum pages: {min(5, max(1, int(args.get('max_pages', 4) or 4)))}"
            if host:
                scope_options.append("domain")
        elif tool == "sandbox_run":
            kind = "sandbox"
            network_access = args.get("network_access") is True
            title = "Run a command with outbound Docker networking?" if network_access else "Run a command in Docker sandbox?"
            summary = ("Execute in a disposable container with GENERAL OUTBOUND BRIDGE NETWORKING enabled for this run."
                       if network_access else "Execute a command in a disposable, offline container")
            command = args.get("command")
            command_json = json.dumps(command if isinstance(command, list) else [], ensure_ascii=False)
            timeout_value = args.get("timeout_seconds", 30)
            if not isinstance(timeout_value, int) or isinstance(timeout_value, bool):
                timeout_value = 30
            timeout_value = min(45, max(1, timeout_value))
            detail = f"Command argv (not a host shell):\n{command_json[:1800]}\n\nWorking directory: {str(args.get('cwd', '.'))[:200]}\nTimeout: {timeout_value} seconds\nThe original workspace is not bind-mounted and no diff is automatically applied."
            if network_access:
                detail += ("\n\nHIGH-RISK NETWORK APPROVAL: this container will use Docker's bridge network. "
                           "Outbound destinations are NOT domain-filtered; package managers, scripts and binaries may contact any reachable public endpoint. "
                           "Review the command before approving. Network access applies to this run only.")
            else:
                detail += "\n\nNetwork is disabled (--network=none)."
        elif tool.startswith("plugin__"):
            title = "Call a local plugin?"
            summary = f"Invoke plugin capability {tool[8:]}"
            try:
                from .tools import redact_sensitive_text
                detail_args = redact_sensitive_text(json.dumps(args, ensure_ascii=False, default=str))
            except Exception:
                detail_args = json.dumps(args, ensure_ascii=False, default=str)
            detail = "Arguments sent to the enabled local service (redacted where recognized):\n" + detail_args[:1800]
        else:
            summary = f"Allow action {tool}"
            detail = "The harness is requesting approval before a capability is used."
        return {"id": uuid.uuid4().hex, "kind": kind, "tool": tool, "title": title,
                "summary": summary, "detail": detail, "host": host,
                "scope_options": scope_options, "created_at": time.time(),
                "expires_in_seconds": APPROVAL_TIMEOUT_SECONDS}

    async def request(self, tool: str, args: dict[str, Any], event_sink: Callable | None = None,
                      audit: Callable | None = None) -> bool:
        if tool in NETWORK_TOOLS:
            with self._lock:
                policy = self.network_policy
                grant_host = None
                if tool in {"web_fetch", "web_crawl"}:
                    grant_host, _ = _display_url(str(args.get("url", "")))
                    has_grant = bool(grant_host and grant_host in self._session_domains)
                else:
                    has_grant = False
            if policy == "deny":
                if audit: audit("permission_denied_by_policy", tool=tool)
                return False
            if has_grant:
                if audit: audit("permission_session_grant_used", tool=tool, host=grant_host)
                return True
        if event_sink is None:
            if audit: audit("permission_denied_no_interactive_session", tool=tool)
            return False
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        public = self._build_request(tool, args)
        with self._lock:
            # Re-check policy at insertion: it may have changed while the request was being
            # assembled. Do not enqueue a new web prompt after the user has switched to Block.
            if tool in NETWORK_TOOLS and self.network_policy == "deny":
                if audit: audit("permission_denied_by_policy", tool=tool)
                return False
            # Avoid unbounded pending futures if clients spam requests or a UI is abandoned.
            if len(self._pending) >= MAX_PENDING_PERMISSIONS:
                if audit: audit("permission_denied_pending_limit", tool=tool)
                return False
            self._pending[public["id"]] = {"public": public, "future": future, "loop": loop}
        if audit:
            audit("permission_requested", permission_id=public["id"], kind=public["kind"], tool=tool, host=public.get("host"))
        try:
            event_sink({"type": "permission_required", "permission": {k: v for k, v in public.items() if k != "created_at"}})
        except Exception:
            with self._lock:
                self._pending.pop(public["id"], None)
            return False
        try:
            result = await asyncio.wait_for(future, timeout=APPROVAL_TIMEOUT_SECONDS)
            return bool(result)
        except asyncio.TimeoutError:
            if audit: audit("permission_timed_out", permission_id=public["id"], tool=tool)
            return False
        except asyncio.CancelledError:
            if audit: audit("permission_cancelled", permission_id=public["id"], tool=tool)
            raise
        finally:
            with self._lock:
                self._pending.pop(public["id"], None)

    def decide(self, permission_id: str, decision: str, scope: str = "once") -> dict[str, Any]:
        if decision not in {"approve", "deny"}:
            raise ValueError("decision must be approve or deny")
        with self._lock:
            row = self._pending.get(permission_id)
            if not row:
                raise KeyError("Permission request expired or no longer exists.")
            public = row["public"]
            if scope not in public["scope_options"]:
                raise ValueError("That permission scope is not available for this request.")
            future: asyncio.Future = row["future"]
            if future.done():
                raise KeyError("Permission request was already decided.")
            approved = decision == "approve"
            effective_decision = decision
            reason = None
            if approved and public.get("tool") in NETWORK_TOOLS and self.network_policy == "deny":
                approved = False
                effective_decision = "deny"
                reason = "network_policy_revoked"
            if approved and scope == "domain" and public.get("host"):
                self._session_domains.add(public["host"])
            # The async API endpoint resolves this future on the same ASGI event loop.
            future.set_result(approved)
            return {"id": permission_id, "decision": effective_decision, "requested_decision": decision,
                    "reason": reason, "scope": scope, "host": public.get("host"),
                    "tool": public.get("tool"), "kind": public.get("kind")}
