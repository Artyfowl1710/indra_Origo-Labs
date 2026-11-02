"""Disposable Windows process-tree fixture; never touches production processes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import psutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=["owner", "child", "leaf", "control", "escaped", "weaker"])
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    directory = args.directory.resolve()
    def record(name, row):
        temporary = directory / (name + ".tmp")
        temporary.write_text(json.dumps(row), encoding="utf-8")
        os.replace(temporary, directory / (name + ".json"))
    def spawn(role, flags=0):
        native = role in {"child", "escaped"}
        arguments = ([str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"),
                      "-NoProfile", "-NonInteractive", "-File", str(ROOT / "scripts/job_native_child.ps1"), role, str(directory)]
                     if native else [sys.executable, "-u", str(Path(__file__).resolve()), role, str(directory)])
        with (directory / (role + "-error.log")).open("ab") as log:
            child = subprocess.Popen(arguments,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log,
                                     creationflags=subprocess.CREATE_NO_WINDOW | flags)
        record(role + "-launcher", {"pid": child.pid, "created": psutil.Process(child.pid).create_time()})
        if native and not flags:
            from origo_runtime.process_lifetime import contain_owned_child
            contain_owned_child(child)
            (directory / "contained").touch()
        return child
    if args.role == "weaker":
        sys.path.insert(0, str(ROOT / "indra/SIH-26/hermes-agent"))
        from hermes_cli.process_identity import attach_self_to_kill_on_close_job
        attached = attach_self_to_kill_on_close_job()
        record("weaker-result", {"attached": attached, "strict_accepted": attach_self_to_kill_on_close_job(strict=True)})
        return
    if args.role == "owner":
        from origo_runtime.process_lifetime import require_owned_process_tree
        require_owned_process_tree()
        require_owned_process_tree()  # Idempotent; never weaken an existing strict job.
    record(args.role, {"pid": os.getpid(), "created": psutil.Process().create_time()})
    if args.role == "owner":
        spawn("child")
        try:
            escaped = spawn("escaped", subprocess.CREATE_BREAKAWAY_FROM_JOB)
            record("breakaway", {"blocked": False, "pid": escaped.pid})
        except OSError as exc:
            record("breakaway", {"blocked": exc.winerror == 5})
        # Capture actual job membership before testing owner death. No source
        # inspection or assumed PPID relationship is used as containment proof.
        deadline = time.monotonic() + 15
        while not (directory / "leaf.json").exists() and time.monotonic() < deadline:
            time.sleep(.05)
        import ctypes
        from ctypes import wintypes
        from hermes_cli import process_identity
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        kernel.QueryInformationJobObject.restype = wintypes.BOOL
        kernel.GetHandleInformation.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetHandleInformation.restype = wintypes.BOOL
        ids = ctypes.create_string_buffer(4096)
        limits = ctypes.create_string_buffer(64 if ctypes.sizeof(ctypes.c_size_t) == 8 else 48)
        flags = wintypes.DWORD()
        handle = process_identity._JOB_HANDLE
        if not kernel.QueryInformationJobObject(handle, 3, ids, len(ids), None): raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.QueryInformationJobObject(handle, 2, limits, len(limits), None): raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.GetHandleInformation(handle, ctypes.byref(flags)): raise ctypes.WinError(ctypes.get_last_error())
        count = int.from_bytes(ids.raw[4:8], "little")
        size = ctypes.sizeof(ctypes.c_size_t)
        members = [int.from_bytes(ids.raw[8 + i * size:8 + (i + 1) * size], "little") for i in range(count)]
        record("job", {"members": members, "handle_inheritable": bool(flags.value & 1),
                       "limit_flags": int.from_bytes(limits.raw[16:20], "little")})
    elif args.role == "child":
        spawn("leaf")
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline and not (args.role == "owner" and (directory / "stop-owner").exists()):
        time.sleep(.1)


if __name__ == "__main__":
    main()
