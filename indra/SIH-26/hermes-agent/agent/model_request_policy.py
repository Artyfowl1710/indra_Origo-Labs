"""Value-returning policy gate, separate from best-effort request observers."""


class ModelRequestBlocked(RuntimeError):
    """Permanent local policy refusal; contains no request content."""


def enforce_model_request(request, **context):
    from hermes_cli import plugins
    try:
        if not plugins.has_hook("pre_model_request"):
            return
        results = plugins.invoke_hook("pre_model_request", request=request, **context)
        for result in results:
            # None is omitted by dispatch. Policies cannot rewrite requests; any
            # unexpected directive is a policy failure, never implicit consent.
            if not isinstance(result, dict) or result.get("action") != "allow":
                raise ModelRequestBlocked("Model request stopped by the local outbound policy. Inspect Audit or Runtime diagnostics.")
    except ModelRequestBlocked:
        raise
    except Exception:
        raise ModelRequestBlocked("Model request stopped because its outbound policy is unavailable.") from None
