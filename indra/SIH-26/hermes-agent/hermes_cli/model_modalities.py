"""Shared model capabilities and prices for pickers and media routing.

Unknown capability and unknown price are explicit states, never text-only/free.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import threading
import time

_unavailable = {}
_availability_lock = threading.Lock()

def _availability_key(provider, model, scope):
    from hermes_constants import get_hermes_home
    return str(get_hermes_home()), provider, model, hashlib.sha256(str(scope or "").encode()).hexdigest()

def mark_unavailable(provider, model, scope=""):
    """Remember a model-specific 404 for ten minutes, scoped to profile and credential."""
    with _availability_lock:
        now = time.monotonic()
        for key in list(_unavailable):
            if _unavailable[key] <= now: _unavailable.pop(key, None)
        if len(_unavailable) >= 1000: _unavailable.pop(next(iter(_unavailable)))
        _unavailable[_availability_key(provider, model, scope)] = now + 600

def _is_unavailable(provider, model, scope):
    with _availability_lock:
        return _unavailable.get(_availability_key(provider, model, scope), 0) > time.monotonic()


def price(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and number >= 0 else None
    except (InvalidOperation, ValueError, TypeError): return None


def describe(provider: str, model: str, config=None) -> dict:
    result = {"input_modalities": [], "output_modalities": [], "modality_known": False,
              "tools": None, "model_kind": "unknown", "chat_compatible": None,
              "prompt_price": None, "completion_price": None}
    try:
        from agent.models_dev import get_model_info
        info = get_model_info(provider, model)
        if info:
            result.update(input_modalities=list(info.input_modalities), output_modalities=list(info.output_modalities), tools=info.tool_call)
            if info.has_cost_data():
                result.update(prompt_price=str(Decimal(str(info.cost_input)) / 1_000_000),
                              completion_price=str(Decimal(str(info.cost_output)) / 1_000_000))
    except Exception: pass
    if provider == "openrouter":
        from hermes_cli.openrouter_catalog import metadata
        item = metadata(model)
        if item:
            architecture = item.get("architecture", {})
            result.update(input_modalities=architecture.get("input_modalities", []),
                          output_modalities=architecture.get("output_modalities", ["text"]))
            params = item.get("supported_parameters")
            if isinstance(params, list): result["tools"] = "tools" in params
            costs = item.get("pricing", {})
            result.update(prompt_price=costs.get("prompt"), completion_price=costs.get("completion"))
    if provider == "gemini":
        from hermes_cli.gemini_catalog import metadata
        item = metadata(model)
        if item:
            methods = item.get("methods", [])
            label = item.get("name", "").lower()
            result["generation_methods"] = methods
            if "embedContent" in methods and "generateContent" not in methods:
                result.update(model_kind="embedding", chat_compatible=False, output_modalities=["embedding"])
            elif any(m.startswith("bidiGenerate") for m in methods):
                result.update(model_kind="live", chat_compatible=False)
            elif "tts" in label:
                result.update(model_kind="speech", chat_compatible=False, output_modalities=["audio"])
            elif "nano banana" in label:
                result.update(model_kind="image generation", chat_compatible=False, output_modalities=["image"])
            elif "generateContent" not in methods:
                result.update(model_kind="specialist", chat_compatible=False)
            else: result["chat_compatible"] = True
    # Explicit metadata on a named self-hosted endpoint overrides public catalogs.
    if config:
        providers = config.get("providers", {})
        name = provider.removeprefix("custom:")
        entry = next((v for k,v in providers.items() if k.lower() == name.lower()), {}) if isinstance(providers,dict) else {}
        per_model = entry.get("models", {}).get(model, {}) if isinstance(entry,dict) and isinstance(entry.get("models"),dict) else {}
        if isinstance(per_model,dict):
            for field in ("display_name", "tools"):
                if field in per_model: result[field] = per_model[field]
            for field in ("input_modalities", "output_modalities"):
                if isinstance(per_model.get(field),list): result[field] = list(per_model[field])
    inputs = result["input_modalities"]; outputs = result["output_modalities"]
    result.update(modality_known=bool(inputs), vision="image" in inputs, video="video" in inputs, audio="audio" in inputs)
    if result["model_kind"] == "unknown" and inputs:
        result["model_kind"] = "multimodal" if any(m != "text" for m in inputs) else "text only"
    if result["chat_compatible"] is None and outputs:
        result["chat_compatible"] = "text" in outputs
    return result


def candidates(provider: str) -> list[dict]:
    if provider == "openrouter":
        from hermes_cli.openrouter_catalog import models
        records = models()
    elif provider == "gemini":
        from hermes_cli.gemini_catalog import cached_models, models
        records = cached_models() or models()
    else: return []
    return [dict(describe(provider, m["id"]), id=m["id"]) for m in records]


def choose(provider: str, main_model: str, modalities, *, explicit_model=None, input_tokens=1000, output_tokens=300, config=None, scope="") -> dict:
    """Keep a capable main model; otherwise explicit reader, then lowest known cost.

    Prices are published estimates, not account-specific free-tier entitlement.
    Routing remains on the selected provider; it never silently changes providers.
    """
    required = set(modalities) | {"text"}
    def capable(item):
        return required <= set(item.get("input_modalities", [])) and item.get("chat_compatible") is not False and "text" in item.get("output_modalities", [])
    if explicit_model:
        explicit = describe(provider, explicit_model, config)
        if not capable(explicit): raise ValueError("The specified reader does not advertise the required input/output modalities")
        return {"provider": provider, "model": explicit_model, "reason": "specified reader", "estimated_cost": None}
    main = describe(provider, main_model, config)
    if capable(main): return {"provider": provider, "model": main_model, "reason": "capable main model", "estimated_cost": None}
    ranked = []
    for item in candidates(provider):
        if _is_unavailable(provider, item["id"], scope): continue
        if not capable(item): continue
        prompt = price(item.get("prompt_price")); completion = price(item.get("completion_price"))
        if prompt is None or completion is None: continue
        estimate = prompt * max(0, input_tokens) + completion * max(0, output_tokens)
        ranked.append((estimate, item["id"]))
    if not ranked: raise ValueError("No capable model with known pricing was found; refresh models or specify a reader")
    estimate, model = min(ranked)
    return {"provider": provider, "model": model, "reason": "lowest known estimated token cost", "estimated_cost": str(estimate)}
