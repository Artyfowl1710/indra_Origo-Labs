"""Small-model amplification primitives. Deterministic controls stay outside model policy.

This module deliberately does not claim to make a model more capable by itself. It
provides bounded typed steps, context budgeting and cheap verifiers that can be
measured against an unamplified baseline.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

STEP_TYPES = {"retrieve", "reason", "compute", "edit", "verify", "summarize"}
MAX_STEPS = 12
MAX_STEP_TEXT = 1200

class ValidationError(ValueError):
    pass

def validate_plan(payload: Any) -> dict[str, Any]:
    """Validate a strict JSON micro-plan; reject unknown keys and unsafe/ambiguous shapes."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Plan must be valid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict) or set(payload) != {"goal", "steps"}:
        raise ValidationError("Plan must contain exactly 'goal' and 'steps'.")
    goal, steps = payload["goal"], payload["steps"]
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 1000:
        raise ValidationError("goal must be a non-empty string of at most 1000 characters.")
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise ValidationError(f"steps must contain 1..{MAX_STEPS} items.")
    normalized = []
    ids = set()
    for i, step in enumerate(steps):
        if not isinstance(step, dict) or set(step) != {"id", "type", "instruction", "verifier"}:
            raise ValidationError(f"step {i} must contain exactly id, type, instruction, verifier.")
        sid, kind, instruction, verifier = step["id"], step["type"], step["instruction"], step["verifier"]
        if not isinstance(sid, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,23}", sid) or sid in ids:
            raise ValidationError(f"step {i} has invalid or duplicate id.")
        if kind not in STEP_TYPES:
            raise ValidationError(f"step {sid} has unsupported type.")
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > MAX_STEP_TEXT:
            raise ValidationError(f"step {sid} instruction must be 1..{MAX_STEP_TEXT} characters.")
        if verifier not in {"nonempty", "json", "tests", "numeric", "manual"}:
            raise ValidationError(f"step {sid} has unsupported verifier.")
        ids.add(sid)
        normalized.append({"id": sid, "type": kind, "instruction": instruction.strip(), "verifier": verifier})
    return {"goal": goal.strip(), "steps": normalized}

def estimate_tokens(text: str) -> int:
    """Conservative, provider-independent estimate; not a tokenizer measurement."""
    if not text:
        return 0
    return max(1, (len(text) + 2) // 3)

def pack_context(items: list[dict[str, Any]], token_budget: int) -> dict[str, Any]:
    """Greedy relevance packing. Stable tie-breaks make the result reproducible."""
    if not isinstance(token_budget, int) or not 1 <= token_budget <= 100_000:
        raise ValueError("token_budget must be between 1 and 100000")
    normalized = []
    for i, item in enumerate(items[:500]):
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            continue
        text = item["text"][:12000]
        try: score = float(item.get("relevance", 0))
        except (TypeError, ValueError): score = 0.0
        if score != score: score = 0.0
        normalized.append((score, str(item.get("source", f"item-{i}"))[:256], text))
    normalized.sort(key=lambda x: (-x[0], x[1]))
    chosen, used = [], 0
    for score, source, text in normalized:
        cost = estimate_tokens(text)
        if used + cost > token_budget:
            remaining = token_budget - used
            if remaining > 0:
                clipped = text[:remaining * 3]
                if clipped:
                    chosen.append({"source": source, "relevance": score, "text": clipped, "estimated_tokens": estimate_tokens(clipped), "truncated": True})
                    used += estimate_tokens(clipped)
            break
        chosen.append({"source": source, "relevance": score, "text": text, "estimated_tokens": cost, "truncated": False})
        used += cost
    return {"items": chosen, "estimated_tokens": used, "token_budget": token_budget,
            "omitted_items": max(0, len(normalized) - len(chosen)),
            "estimator": "ceil(chars/3); approximate, not provider-tokenizer exact"}

def _safe_arithmetic(expr: str) -> float:
    """Evaluate a small arithmetic expression without eval or names/calls."""
    if not isinstance(expr, str) or len(expr) > 200:
        raise ValueError("expression must be <= 200 characters")
    tree = ast.parse(expr, mode="eval")
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub,
               ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.USub, ast.UAdd, ast.Load)
    nodes = list(ast.walk(tree))
    if len(nodes) > 80 or any(not isinstance(n, allowed) for n in nodes):
        raise ValueError("expression contains unsupported syntax")
    for n in nodes:
        if isinstance(n, ast.Constant) and (isinstance(n.value, bool) or not isinstance(n.value, (int, float))):
            raise ValueError("only numeric constants are allowed")
    # Bound exponentiation and numeric magnitude before interpreting.
    for n in ast.walk(tree):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow):
            if not isinstance(n.right, ast.Constant) or not isinstance(n.right.value, (int, float)) or abs(n.right.value) > 12:
                raise ValueError("power exponent must be a literal with absolute value <= 12")
    value = _eval_node(tree.body)
    if abs(value) > 1e100:
        raise ValueError("result magnitude exceeds verifier limit")
    return value

def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant): return float(node.value)
    if isinstance(node, ast.UnaryOp):
        v = _eval_node(node.operand)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp):
        a, b = _eval_node(node.left), _eval_node(node.right)
        if isinstance(node.op, ast.Add): return a + b
        if isinstance(node.op, ast.Sub): return a - b
        if isinstance(node.op, ast.Mult): return a * b
        if isinstance(node.op, ast.Div): return a / b
        if isinstance(node.op, ast.Mod): return a % b
        if isinstance(node.op, ast.Pow): return a ** b
    raise ValueError("unsupported expression")

def verify_result(verifier: str, result: Any, expected: Any = None) -> dict[str, Any]:
    """Cheap deterministic verifier; 'manual' is explicitly not a pass."""
    if verifier == "nonempty":
        ok = result is not None and bool(str(result).strip())
        return {"status": "pass" if ok else "fail", "verifier": verifier, "detail": "result is non-empty" if ok else "result is empty"}
    if verifier == "json":
        try: parsed = json.loads(result) if isinstance(result, str) else result
        except (ValueError, TypeError): parsed = None
        ok = isinstance(parsed, (dict, list))
        return {"status": "pass" if ok else "fail", "verifier": verifier, "detail": "valid JSON object/array" if ok else "not valid JSON object/array"}
    if verifier == "numeric":
        try:
            actual = float(result)
            target = float(expected)
            ok = abs(actual - target) <= max(1e-9, abs(target) * 1e-9)
        except (TypeError, ValueError):
            ok = False
        return {"status": "pass" if ok else "fail", "verifier": verifier, "expected": expected, "actual": result}
    if verifier == "tests":
        if not isinstance(result, dict) or not isinstance(result.get("passed"), int) or not isinstance(result.get("failed"), int):
            return {"status": "fail", "verifier": verifier, "detail": "expected {passed:int, failed:int}"}
        ok = result["passed"] > 0 and result["failed"] == 0
        return {"status": "pass" if ok else "fail", "verifier": verifier, "detail": result}
    if verifier == "manual":
        return {"status": "needs_review", "verifier": verifier, "detail": "No deterministic verifier is defined."}
    raise ValueError("unknown verifier")

@dataclass
class TokenBudget:
    limit: int = 4096
    used_estimate: int = 0
    def __post_init__(self):
        if not 1 <= self.limit <= 1_000_000: raise ValueError("limit must be 1..1000000")
    def account(self, text: str) -> dict[str, int | bool]:
        cost = estimate_tokens(text)
        self.used_estimate += cost
        return {"estimated_tokens": cost, "used_estimate": self.used_estimate,
                "remaining_estimate": max(0, self.limit - self.used_estimate), "over_budget": self.used_estimate > self.limit}

def capability_profile(results: dict[str, Any]) -> dict[str, Any]:
    """Summarize measured probe outcomes without inventing scores for missing probes."""
    allowed = {"json_adherence", "tool_call_accuracy", "recall", "arithmetic"}
    probes = {}
    for key, value in results.items():
        if key not in allowed: continue
        if isinstance(value, dict) and isinstance(value.get("passed"), int) and isinstance(value.get("total"), int) and value["total"] > 0 and 0 <= value["passed"] <= value["total"]:
            probes[key] = {"passed": value["passed"], "total": value["total"], "rate": value["passed"] / value["total"]}
    canonical = json.dumps(probes, sort_keys=True, separators=(",", ":"))
    return {"schema_version": 1, "probes": probes, "profile_hash": hashlib.sha256(canonical.encode()).hexdigest(),
            "status": "measured" if probes else "unprobed", "selection_policy": "profile is advisory; hard safety limits are never relaxed by scores"}


def verify_arithmetic(expression: str, claimed: Any, tolerance: float = 1e-9) -> dict[str, Any]:
    """Recompute a bounded arithmetic expression without eval; no names or function calls."""
    try:
        actual = _safe_arithmetic(expression)
        claimed_value = float(claimed)
        if not isinstance(tolerance, (int, float)) or tolerance < 0 or tolerance > 1e-3:
            raise ValueError("tolerance must be between 0 and 0.001")
        ok = abs(actual - claimed_value) <= max(float(tolerance), abs(actual) * float(tolerance))
        return {"status": "pass" if ok else "fail", "verifier": "arithmetic_recompute",
                "expression": expression, "recomputed": actual, "claimed": claimed_value,
                "tolerance": tolerance}
    except (ValueError, TypeError, SyntaxError, ZeroDivisionError, OverflowError) as exc:
        return {"status": "fail", "verifier": "arithmetic_recompute", "detail": str(exc)}
