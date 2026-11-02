"""Require kernel-owned child cleanup before starting long-lived services."""
import os
from pathlib import Path
import sys


def require_owned_process_tree():
    if os.name != "nt":
        raise RuntimeError("This service runtime requires Windows process containment")
    core = Path(__file__).resolve().parents[1] / "indra/SIH-26/hermes-agent"
    if str(core) not in sys.path:
        sys.path.insert(0, str(core))
    from hermes_cli.process_identity import attach_self_to_kill_on_close_job
    if not attach_self_to_kill_on_close_job(strict=True):
        raise RuntimeError("Windows could not establish owned child-process cleanup; service startup was refused")


def contain_owned_child(process):
    """Attach a Popen/asyncio child using its existing Windows creation handle.

    CPython's Windows Popen handle is intentionally used here instead of a
    PID lookup. Compatibility is covered by real-process tests on the bundled
    runtime and must be rechecked when the packaged Python runtime changes.
    """
    require_owned_process_tree()
    from hermes_cli.process_identity import assign_child_handle_to_owned_job
    transport = getattr(process, "_transport", None)
    popen = transport.get_extra_info("subprocess") if transport is not None else process
    handle = getattr(popen, "_handle", None)
    if handle is None or not assign_child_handle_to_owned_job(int(handle)):
        raise RuntimeError("Windows could not contain the owned service process; startup was refused")
