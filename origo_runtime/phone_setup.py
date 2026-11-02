"""Native setup bridge: bounded JSON over stdin, never passwords in argv/logs."""
import argparse
import json
from pathlib import Path
import sys

from .phone_config import save_settings, read_settings, disable_settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("action", choices=["read", "save", "disable"])
    args = parser.parse_args()
    try:
        if args.action == "save":
            raw = sys.stdin.buffer.read(8193)
            if len(raw) > 8192:
                raise ValueError("Phone setup is oversized")
            result = save_settings(args.home, json.loads(raw))
        elif args.action == "disable":
            disable_settings(args.home)
            result = read_settings(args.home)
        else:
            result = read_settings(args.home)
        print(json.dumps({"ok": True, "settings": result}))
    except (ValueError, OSError, ImportError):
        print(json.dumps({"ok": False, "error": "Phone setup could not be saved. Check the address, password and profile permissions."}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
