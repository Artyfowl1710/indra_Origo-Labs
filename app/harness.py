"""Deterministic control-plane primitives for an agent run.

The model proposes actions; this module owns execution limits and run state.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

ALLOWED_TRANSITIONS = {
    "created": {"running", "failed"},
    "running": {"completed", "failed", "provider_error", "step_limit", "tool_limit", "time_limit", "cancelled"},
    "completed": set(), "failed": set(), "step_limit": set(),
    "tool_limit": set(), "time_limit": set(), "cancelled": set(), "provider_error": set(),
}


def _int_env(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(low, min(high, value))


@dataclass
class RunBudget:
    max_steps: int = field(default_factory=lambda: _int_env("INDRA_MAX_STEPS", 14, 1, 40))
    max_tool_calls: int = field(default_factory=lambda: _int_env("INDRA_MAX_TOOL_CALLS", 32, 1, 100))
    max_duration_seconds: int = field(default_factory=lambda: _int_env("INDRA_MAX_RUN_SECONDS", 240, 5, 1800))
    max_result_chars: int = field(default_factory=lambda: _int_env("INDRA_MAX_TOOL_RESULT_CHARS", 12000, 500, 100000))
    profile: str = "balanced"
    started: float = field(default_factory=time.monotonic)
    steps: int = 0
    tool_calls: int = 0

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def time_exhausted(self) -> bool:
        return self.elapsed() >= self.max_duration_seconds

    def clip_result(self, result: Any) -> Any:
        """Bound tool output before it enters the model context or saved trace."""
        import json
        try:
            raw = json.dumps(result, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            raw = str(result)
        if len(raw) <= self.max_result_chars:
            return result
        return {
            "truncated": True,
            "original_chars": len(raw),
            "preview": raw[: self.max_result_chars],
            "message": "Tool output was truncated by the harness output budget.",
        }


class RunState:
    def __init__(self, run_id: str, store):
        self.run_id = run_id
        self.store = store
        self.status = "created"

    def transition(self, status: str, **fields):
        if status not in ALLOWED_TRANSITIONS.get(self.status, set()):
            raise ValueError(f"Invalid run state transition: {self.status} -> {status}")
        previous = self.status
        self.status = status
        self.store.event("run_state_changed", run_id=self.run_id, previous=previous, status=status, **fields)
        return status


PROFILE_LIMITS = {
    "fast": {"steps": 3, "tools": 5, "seconds": 45},
    "balanced": {"steps": 8, "tools": 16, "seconds": 120},
    "deep": {"steps": 14, "tools": 32, "seconds": 240},
}

def choose_profile(task: str) -> str:
    """Transparent deterministic routing; never lets the model choose its own safety limits."""
    override = os.getenv("INDRA_PROFILE", "auto").strip().lower()
    if override in PROFILE_LIMITS:
        return override
    text = (task or "").lower()
    deep_signals = ("debug", "implement", "refactor", "review", "audit", "research", "experiment", "architecture", "inspect workspace", "compare", "trace", "fix", "test", "benchmark", "analyze")
    fast_signals = ("what is ", "define ", "summarize this ", "quickly explain", "one sentence", "just tell me", "convert ", "format ")
    if any(signal in text for signal in deep_signals): return "deep"
    if any(signal in text for signal in fast_signals) and len(text) < 500: return "fast"
    return "balanced"

def budget_for_task(task: str) -> RunBudget:
    profile = choose_profile(task); limits = PROFILE_LIMITS[profile]
    # Global environment values are hard ceilings, even for the deep profile.
    return RunBudget(
        max_steps=min(limits["steps"], _int_env("INDRA_MAX_STEPS", 14, 1, 40)),
        max_tool_calls=min(limits["tools"], _int_env("INDRA_MAX_TOOL_CALLS", 32, 1, 100)),
        max_duration_seconds=min(limits["seconds"], _int_env("INDRA_MAX_RUN_SECONDS", 240, 5, 1800)),
        max_result_chars=_int_env("INDRA_MAX_TOOL_RESULT_CHARS", 12000, 500, 100000),
        profile=profile,
    )
