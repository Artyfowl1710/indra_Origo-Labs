"""Private phone-sharing settings; uses the imported dashboard auth provider."""
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
from urllib.parse import urlsplit

from dotenv import dotenv_values, set_key

SETTINGS_NAME = "phone-access.json"
SECRET_ENV = "HERMES_DASHBOARD_BASIC_AUTH_SECRET"
HASH_ENV = "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH"
USER_ENV = "HERMES_DASHBOARD_BASIC_AUTH_USERNAME"


def normalize_endpoint(value):
    if not isinstance(value, str) or len(value) > 300 or any(ord(c) < 32 for c in value):
        raise ValueError("Enter a root HTTPS Tailscale address")
    try:
        uri = urlsplit(value.strip())
        host = uri.hostname or ""
        if (uri.scheme != "https" or uri.username is not None or uri.password is not None
                or uri.port not in (None, 443) or uri.path not in ("", "/")
                or uri.query or uri.fragment or "?" in value or "#" in value):
            raise ValueError()
        if not host.endswith(".ts.net") or len(host) > 253:
            raise ValueError()
        if not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split(".")):
            raise ValueError()
    except ValueError as exc:
        raise ValueError("Use your workstation's HTTPS .ts.net root address, without paths or custom ports") from exc
    return "https://" + host


def read_settings(home: Path):
    path = home / SETTINGS_NAME
    if not path.exists():
        return None
    if path.stat().st_size > 4096:
        raise ValueError("Phone settings are oversized")
    row = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(row, dict) or not isinstance(row.get("enabled"), bool):
        raise ValueError("Phone settings are invalid")
    endpoint = normalize_endpoint(row.get("endpoint"))
    port = row.get("port")
    username = row.get("username")
    if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
        raise ValueError("Phone sharing port must be between 1024 and 65535")
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", username):
        raise ValueError("Use a username with letters, numbers, dots, dashes or underscores")
    return {"version": 1, "enabled": row["enabled"], "endpoint": endpoint, "port": port, "username": username}


def _write_settings(home, row):
    home.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=home, prefix=".phone-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(row, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, home / SETTINGS_NAME)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def save_settings(home: Path, payload):
    if not isinstance(payload, dict) or set(payload) != {"endpoint", "username", "password", "port"}:
        raise ValueError("Invalid phone setup fields")
    endpoint = normalize_endpoint(payload["endpoint"])
    username, password, port = payload["username"], payload["password"], payload["port"]
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", username):
        raise ValueError("Use a username with letters, numbers, dots, dashes or underscores")
    if not isinstance(password, str) or not 12 <= len(password) <= 256:
        raise ValueError("Use a password between 12 and 256 characters")
    if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
        raise ValueError("Phone sharing port must be between 1024 and 65535")
    core = Path(__file__).resolve().parents[1] / "indra/SIH-26/hermes-agent"
    if str(core) not in sys.path:
        sys.path.insert(0, str(core))
    from plugins.dashboard_auth.basic import hash_password
    password_hash = hash_password(password)
    home.mkdir(parents=True, exist_ok=True)
    env = str(home / ".env")
    # Update credentials before publishing the settings atomically. An interrupted
    # update may revoke sessions; it cannot create an unauthenticated deployment.
    for key, value in {USER_ENV: username, HASH_ENV: password_hash, SECRET_ENV: secrets.token_urlsafe(48),
                       "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD": ""}.items():
        set_key(env, key, value, quote_mode="always")
    row = {"version": 1, "enabled": True, "endpoint": endpoint, "port": port, "username": username}
    _write_settings(home, row)
    return row


def disable_settings(home: Path):
    row = read_settings(home)
    if row is None:
        return
    row["enabled"] = False
    set_key(str(home / ".env"), SECRET_ENV, secrets.token_urlsafe(48), quote_mode="always")
    _write_settings(home, row)


def apply_settings(home: Path, config):
    row = read_settings(home)
    if row is None:
        return config
    env = dotenv_values(home / ".env")
    if not str(env.get(HASH_ENV) or "").startswith("scrypt$") or len(str(env.get(SECRET_ENV) or "")) < 32 or env.get(USER_ENV) != row["username"]:
        raise ValueError("Phone credentials are missing or inconsistent; open Phone pairing to configure them again")
    # Keep sign-in protection after disabling sharing. Removing a proxy or
    # switching ports must never turn an old authenticated endpoint into a bare one.
    dashboard = config.setdefault("dashboard", {})
    if not isinstance(dashboard, dict):
        raise ValueError("Dashboard configuration is invalid")
    dashboard["public_url"] = row["endpoint"]
    dashboard["basic_auth"] = {"username": row["username"], "password_hash": env[HASH_ENV], "session_ttl_seconds": 43200}
    return config
