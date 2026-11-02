"""Local-first research provenance: signed Capsules and a conservative Proof Ledger.

Capsules are passive ZIP archives: verification never executes archived code. A
signature proves integrity under the included Ed25519 public key; trust still
requires comparing its fingerprint to a known/pinned fingerprint.

Proof Ledger links claims to user-selected, locally readable evidence. It checks
exact excerpts and numeric consistency, but does not pretend to prove semantic
entailment for arbitrary natural-language claims.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import threading
import functools
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

MAX_CAPSULE_FILES = 250
MAX_CAPSULE_BYTES = 20 * 1024 * 1024
MAX_ARCHIVE_UNPACKED = 50 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 600
EXCLUDED_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".next", "secrets", "credentials", ".ssh", ".aws", ".azure", ".gcloud", ".gnupg", ".config", "keys", "private_keys"}
EXCLUDED_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "secrets.json", "credentials.json", "service_account.json", "token.json", "auth.json", "credentials", ".netrc", ".npmrc", ".pypirc", "cookies.txt", "known_hosts"}
SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".sqlite", ".sqlite3", ".db", ".log", ".der")
SECRET_PATTERNS = (re.compile(r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*[:=]\s*[\"\']?[^\s\"\']{8,}"), re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{20,}"))
NUMERIC_RE = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)*(?:%|×|x)?")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _fingerprint(public_key_bytes: bytes) -> str:
    return _sha(public_key_bytes)


def _checked_workspace_file(workspace: Path, relative_path: str) -> Path:
    """Resolve a selected path without traversing symlinks, while staying in the workspace."""
    root = Path(workspace).resolve(strict=True)
    rel = PurePosixPath(relative_path)
    cursor = root
    for part in rel.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("Symlinks are not allowed for Capsule or Proof Ledger paths.")
    target = cursor.resolve(strict=True)
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError("Selected path must be a regular file inside the workspace.")
    return target


def _safe_relpath(raw: str) -> str:
    path = PurePosixPath(str(raw).replace("\\", "/"))
    if not raw or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Path must be a non-empty workspace-relative path without traversal segments.")
    if any(part.lower() in EXCLUDED_PARTS for part in path.parts):
        raise ValueError("This path is excluded from Capsules because it may contain runtime or sensitive data.")
    name = path.name.lower()
    if name in EXCLUDED_NAMES or name.endswith(SENSITIVE_SUFFIXES) or name.startswith(".env"):
        raise ValueError("This file type/name is excluded from Capsules because it may contain secrets or runtime state.")
    return path.as_posix()


class CapsuleService:
    def __init__(self, data_root: Path):
        self.data_root = Path(data_root).resolve()
        self.root = self.data_root / "capsules"
        self.root.mkdir(parents=True, exist_ok=True)
        self.private_key_path = self.data_root / "capsule_signing_key.pem"
        self._private_key = self._load_or_create_key()
        self.public_key = self._private_key.public_key()
        self.public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.fingerprint = _fingerprint(self.public_bytes)

    def _load_or_create_key(self) -> Ed25519PrivateKey:
        if self.private_key_path.exists():
            key = serialization.load_pem_private_key(self.private_key_path.read_bytes(), password=None)
            if not isinstance(key, Ed25519PrivateKey):
                raise RuntimeError("Capsule signing key is not Ed25519.")
            return key
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        fd = os.open(self.private_key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "wb") as handle:
            handle.write(pem)
            handle.flush()
            os.fsync(handle.fileno())
        return key

    def create(self, workspace: Path, *, run: dict | None, events: list[dict], paths: list[str]) -> dict[str, Any]:
        workspace = Path(workspace).resolve(strict=True)
        if len(paths) > MAX_CAPSULE_FILES:
            raise ValueError(f"Capsule selection exceeds {MAX_CAPSULE_FILES} files.")
        payload: dict[str, bytes] = {}
        total = 0
        for raw in paths:
            rel = _safe_relpath(raw)
            try:
                target = _checked_workspace_file(workspace, rel)
            except (OSError, ValueError) as exc:
                raise ValueError(f"Selected path is not a safe regular workspace file ({rel}): {exc}") from exc
            size = target.stat().st_size
            if size > MAX_CAPSULE_BYTES:
                raise ValueError(f"File exceeds per-file capsule limit: {rel}")
            data = target.read_bytes()
            if any(pattern.search(data.decode("utf-8", errors="ignore")) for pattern in SECRET_PATTERNS):
                raise ValueError(f"Likely secret material detected; remove it before packaging: {rel}")
            total += len(data)
            if total > MAX_CAPSULE_BYTES:
                raise ValueError(f"Selected files exceed total capsule limit ({MAX_CAPSULE_BYTES} bytes).")
            payload[f"workspace/{rel}"] = data

        run_metadata = None
        if run:
            # Store a shallow allowlist, not arbitrary payloads that may contain prompts/secrets.
            run_metadata = {key: run.get(key) for key in ("run_id", "created_at", "status", "mode", "model", "duration_ms") if key in run}
        event_metadata = []
        for event in events[:200]:
            if not isinstance(event, dict):
                continue
            # Events contain metadata only in this archive export; content fields are deliberately omitted.
            safe = {key: event.get(key) for key in ("event_id", "timestamp", "type", "run_id", "status", "step", "tool") if key in event}
            if safe:
                event_metadata.append(safe)
        manifest = {
            "format": "indra-origo-capsule-v1",
            "created_at": _now(),
            "capsule_id": uuid.uuid4().hex,
            "run": run_metadata,
            "events": event_metadata,
            "files": [{"path": path, "size": len(data), "sha256": _sha(data)} for path, data in sorted(payload.items())],
            "signing": {"algorithm": "Ed25519", "public_key_format": "raw-32-byte-base64", "fingerprint_sha256": self.fingerprint},
            "limits": {"selected_files": MAX_CAPSULE_FILES, "selected_bytes": MAX_CAPSULE_BYTES},
        }
        signature = self._private_key.sign(_canonical(manifest))
        public_key_pem = self.public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("capsule_manifest.json", _canonical(manifest))
            archive.writestr("signature.ed25519", signature)
            archive.writestr("signer_public_key.pem", public_key_pem)
            for path, data in sorted(payload.items()):
                archive.writestr(path, data)
        filename = f"{manifest['capsule_id']}.zip"
        destination = self.root / filename
        temporary = self.root / f".{filename}.tmp"
        temporary.write_bytes(buffer.getvalue())
        os.replace(temporary, destination)
        return {"capsule_id": manifest["capsule_id"], "filename": filename, "size_bytes": destination.stat().st_size,
                "file_count": len(payload), "fingerprint_sha256": self.fingerprint,
                "download_url": f"/api/capsules/{manifest['capsule_id']}/download", "created_at": manifest["created_at"]}

    def list(self) -> list[dict[str, Any]]:
        results = []
        for path in sorted(self.root.glob("*.zip"), key=lambda item: item.stat().st_mtime, reverse=True)[:100]:
            try:
                with zipfile.ZipFile(path) as archive:
                    infos = archive.infolist()
                    if len(infos) > MAX_ARCHIVE_ENTRIES:
                        continue
                    manifest_info = archive.getinfo("capsule_manifest.json")
                    if manifest_info.file_size > 1_000_000 or sum(info.file_size for info in infos) > MAX_ARCHIVE_UNPACKED:
                        continue
                    manifest = json.loads(archive.read("capsule_manifest.json"))
                results.append({"capsule_id": manifest.get("capsule_id"), "created_at": manifest.get("created_at"),
                                "file_count": len(manifest.get("files", [])), "size_bytes": path.stat().st_size,
                                "fingerprint_sha256": manifest.get("signing", {}).get("fingerprint_sha256"),
                                "download_url": f"/api/capsules/{manifest.get('capsule_id')}/download"})
            except (OSError, ValueError, KeyError, zipfile.BadZipFile, json.JSONDecodeError):
                continue
        return results

    def path_for(self, capsule_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", capsule_id):
            raise ValueError("Invalid capsule ID.")
        path = self.root / f"{capsule_id}.zip"
        if not path.is_file():
            raise FileNotFoundError("Capsule not found.")
        return path

    def verify(self, archive_path: Path) -> dict[str, Any]:
        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                infos = archive.infolist()
                if len(infos) > MAX_ARCHIVE_ENTRIES:
                    raise ValueError("Archive has too many entries.")
                names = [info.filename for info in infos]
                if len(names) != len(set(names)):
                    raise ValueError("Archive has duplicate entry names.")
                total_unpacked = sum(info.file_size for info in infos)
                if total_unpacked > MAX_ARCHIVE_UNPACKED:
                    raise ValueError("Archive expands beyond the verification size limit.")
                for name in names:
                    path = PurePosixPath(name)
                    if path.is_absolute() or any(part in {"..", ""} for part in path.parts):
                        raise ValueError("Archive contains an unsafe path.")
                manifest_bytes = archive.read("capsule_manifest.json")
                manifest = json.loads(manifest_bytes)
                signature = archive.read("signature.ed25519")
                public_key = serialization.load_pem_public_key(archive.read("signer_public_key.pem"))
                if not isinstance(public_key, Ed25519PublicKey):
                    raise ValueError("Capsule signer is not Ed25519.")
                manifest_valid = manifest.get("format") == "indra-origo-capsule-v1"
                if not manifest_valid:
                    raise ValueError("Unsupported Capsule manifest format.")
                public_raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
                fingerprint = _fingerprint(public_raw)
                declared_fingerprint = manifest.get("signing", {}).get("fingerprint_sha256")
                signature_valid = False
                try:
                    public_key.verify(signature, _canonical(manifest))
                    signature_valid = True
                except Exception:
                    signature_valid = False
                expected = {item["path"]: item for item in manifest.get("files", [])}
                problems = []
                if declared_fingerprint != fingerprint:
                    problems.append("signer_fingerprint_mismatch")
                if not isinstance(manifest.get("files"), list):
                    raise ValueError("Capsule manifest file list is malformed.")
                for path, item in expected.items():
                    if path not in names:
                        problems.append(f"missing:{path}")
                        continue
                    data = archive.read(path)
                    if _sha(data) != item.get("sha256") or len(data) != item.get("size"):
                        problems.append(f"hash_mismatch:{path}")
                payload_names = set(names) - {"capsule_manifest.json", "signature.ed25519", "signer_public_key.pem"}
                extra = sorted(payload_names - set(expected))
                if extra:
                    problems.extend(f"unmanifested:{path}" for path in extra)
                try:
                    local_trusted = fingerprint == self.fingerprint
                except Exception:
                    local_trusted = False
                return {"valid": bool(signature_valid and not problems), "signature_valid": signature_valid,
                        "manifest_valid": manifest_valid, "files_valid": not problems, "problems": problems,
                        "signer_fingerprint_sha256": fingerprint, "signer_trusted_by_this_install": local_trusted,
                        "trust_note": "A valid signature verifies integrity under this archive's public key. Trust requires an independently known/pinned fingerprint."}
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, OSError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            return {"valid": False, "signature_valid": False, "manifest_valid": False, "files_valid": False,
                    "problems": [f"unreadable_or_incomplete_archive:{type(exc).__name__}"],
                    "signer_trusted_by_this_install": False}


def _serialized(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


class ProofLedger:
    def __init__(self, store):
        self.store = store
        self._lock = threading.RLock()

    def _read(self) -> dict[str, list[dict[str, Any]]]:
        value = self.store.get_setting("proof_ledger_v1", {"evidence": [], "claims": []})
        if not isinstance(value, dict):
            value = {"evidence": [], "claims": []}
        value.setdefault("evidence", [])
        value.setdefault("claims", [])
        return value

    @_serialized
    def add_evidence(self, workspace: Path, path: str, excerpt: str, note: str = "") -> dict[str, Any]:
        rel = _safe_relpath(path)
        workspace = Path(workspace).resolve(strict=True)
        target = _checked_workspace_file(workspace, rel)
        if target.stat().st_size > 2_000_000:
            raise ValueError("Evidence source exceeds the 2 MB limit.")
        source_bytes = target.read_bytes()
        try:
            content = source_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Evidence source must be UTF-8 text.") from exc
        excerpt = excerpt.strip()
        if not excerpt or len(excerpt) > 3000 or excerpt not in content:
            raise ValueError("Evidence excerpt must be non-empty and match the selected file exactly.")
        if any(pattern.search(excerpt) for pattern in SECRET_PATTERNS):
            raise ValueError("Evidence excerpt appears to contain credentials or private-key material; redact it before registering evidence.")
        data = self._read()
        if len(data["evidence"]) >= 1000:
            raise ValueError("Proof Ledger evidence limit reached.")
        item = {"evidence_id": uuid.uuid4().hex, "created_at": _now(), "path": rel,
                "source_sha256": _sha(source_bytes), "excerpt": excerpt, "note": note[:500],
                "scope": "exact excerpt found in local file; semantic claim support not automatically established"}
        data["evidence"].append(item)
        self.store.set_setting("proof_ledger_v1", data)
        return item

    @_serialized
    def add_claim(self, statement: str, evidence_ids: list[str], workspace: Path | None = None) -> dict[str, Any]:
        statement = statement.strip()
        if not statement or len(statement) > 3000:
            raise ValueError("Claim must contain 1–3000 characters.")
        data = self._read()
        known = {item["evidence_id"]: item for item in data["evidence"]}
        attached = [known[item] for item in evidence_ids if item in known]
        missing = sorted(set(evidence_ids) - set(known))
        stale = []
        if workspace is not None:
            root = Path(workspace).resolve()
            for item in attached:
                try:
                    rel = _safe_relpath(item["path"])
                    source = _checked_workspace_file(root, rel)
                    if _sha(source.read_bytes()) != item.get("source_sha256"):
                        stale.append(item["evidence_id"])
                except (OSError, ValueError, KeyError):
                    stale.append(item["evidence_id"])
        numeric_values = NUMERIC_RE.findall(statement)
        evidence_numeric_values = {number for evidence in attached for number in NUMERIC_RE.findall(evidence["excerpt"])}
        mismatches = [number for number in numeric_values if number not in evidence_numeric_values]
        if missing or not attached:
            status = "unsupported"
        elif stale:
            status = "stale_evidence"
        elif mismatches:
            status = "numeric_mismatch"
        elif numeric_values:
            status = "numeric_match_semantics_unverified"
        else:
            status = "human_review_required"
        claim = {"claim_id": uuid.uuid4().hex, "created_at": _now(), "statement": statement,
                 "evidence_ids": [item["evidence_id"] for item in attached], "missing_evidence_ids": missing, "stale_evidence_ids": stale,
                 "numeric_values": numeric_values, "status": status,
                 "limitation": "Evidence links and numeric-token checks are not semantic entailment or truth verification."}
        if len(data["claims"]) >= 1000:
            raise ValueError("Proof Ledger claim limit reached.")
        data["claims"].append(claim)
        self.store.set_setting("proof_ledger_v1", data)
        return claim

    @_serialized
    def lint(self, text: str, claim_ids: list[str] | None = None, workspace: Path | None = None) -> dict[str, Any]:
        data = self._read()
        by_id = {item["claim_id"]: item for item in data["claims"]}
        selected = [by_id[cid] for cid in (claim_ids or list(by_id.keys())) if cid in by_id]
        missing_ids = sorted(set(claim_ids or []) - set(by_id))
        text_numbers = NUMERIC_RE.findall(text)
        findings = []
        for claim in selected:
            found = claim["statement"] in text
            status = claim["status"]
            if workspace is not None and claim.get("evidence_ids"):
                evidence_map = {item["evidence_id"]: item for item in data["evidence"]}
                root = Path(workspace).resolve()
                stale = False
                for evidence_id in claim["evidence_ids"]:
                    item = evidence_map.get(evidence_id)
                    if not item:
                        stale = True
                        break
                    try:
                        rel = _safe_relpath(item["path"])
                        source = _checked_workspace_file(root, rel)
                        if _sha(source.read_bytes()) != item.get("source_sha256"):
                            stale = True
                            break
                    except (OSError, ValueError, KeyError):
                        stale = True
                        break
                if stale:
                    status = "stale_evidence"
            if not found:
                finding_status = "claim_not_found_in_text"
            elif status == "numeric_match_semantics_unverified":
                finding_status = "review_required"
            else:
                finding_status = status
            findings.append({"claim_id": claim["claim_id"], "statement": claim["statement"], "status": finding_status,
                             "evidence_ids": claim["evidence_ids"], "included_in_text": found})
        flagged = [item for item in findings if item["status"] not in {"reviewed_by_human"}]
        return {"status": "review_required" if flagged or missing_ids else "pass", "export_allowed": not flagged and not missing_ids,
                "summary": {"claims_checked": len(findings), "flagged": len(flagged), "missing_claim_ids": len(missing_ids)},
                "text_numeric_tokens": text_numbers, "findings": findings, "missing_claim_ids": missing_ids,
                "limitations": ["This linter does not automatically discover every factual claim in prose.",
                                "Numeric token matching is lexical, not a statistical test or semantic verification.",
                                "Human-reviewed status is a workflow attestation, not proof that a claim is true."]}

    @_serialized
    def review_claim(self, claim_id: str, reviewed: bool, workspace: Path | None = None) -> dict[str, Any]:
        data = self._read()
        item = next((claim for claim in data["claims"] if claim.get("claim_id") == claim_id), None)
        if item is None:
            raise KeyError("Claim was not found.")
        if reviewed:
            status = item.get("status")
            if workspace is not None and item.get("evidence_ids"):
                root = Path(workspace).resolve()
                by_id = {record["evidence_id"]: record for record in data["evidence"]}
                for evidence_id in item["evidence_ids"]:
                    record = by_id.get(evidence_id)
                    try:
                        rel = _safe_relpath(record["path"]) if record else ""
                        source = _checked_workspace_file(root, rel)
                        if not record or _sha(source.read_bytes()) != record.get("source_sha256"):
                            status = "stale_evidence"
                            break
                    except (OSError, ValueError, KeyError):
                        status = "stale_evidence"
                        break
            if status in {"unsupported", "numeric_mismatch", "stale_evidence"} or not item.get("evidence_ids"):
                raise ValueError("Claims with missing, mismatched, or stale evidence cannot be cleared by acknowledgement. Fix the evidence first.")
            item["status"] = "reviewed_by_human"
            item["reviewed_at"] = _now()
            item["review_note"] = "User explicitly marked this claim as reviewed; this is not a guarantee of truth."
        else:
            item["status"] = "human_review_required" if item.get("evidence_ids") else "unsupported"
            item.pop("reviewed_at", None)
            item.pop("review_note", None)
        self.store.set_setting("proof_ledger_v1", data)
        return item

    @_serialized
    def get(self) -> dict[str, Any]:
        data = self._read()
        return {"evidence": data["evidence"][-100:], "claims": data["claims"][-100:],
                "scope": "local evidence registry; no semantic entailment claim"}
