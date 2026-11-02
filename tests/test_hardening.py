import asyncio
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app.store import Store
import app.tools as tools
import app.main as main_module
from app.agent import Agent
from app.providers import OpenAICompatibleProvider, ProviderError


class WorkspaceHardeningTests(unittest.TestCase):
    def test_secret_files_are_excluded_from_read_search_inventory_and_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("API_KEY=never-read-this", encoding="utf-8")
            (root / "service_account.json").write_text('{"token":"never-read-this"}', encoding="utf-8")
            (root / "normal.md").write_text("Safe project documentation", encoding="utf-8")
            with patch.object(tools, "WORKSPACE", root):
                self.assertIn("error", tools.read_file(".env"))
                search = tools.search_files("never-read-this")
                self.assertEqual(search["matches"], [])
                inventory_paths = {row["path"] for row in tools.workspace_inventory()}
                self.assertIn("normal.md", inventory_paths)
                self.assertNotIn(".env", inventory_paths)
                pack = tools.build_context_pack()
                self.assertNotIn("never-read-this", pack["context"])
                self.assertNotIn(".env", pack["files_included"])

    def test_dependency_directories_are_pruned_before_scanning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dep = root / "node_modules" / "huge-package"
            dep.mkdir(parents=True)
            for index in range(100):
                (dep / f"file{index}.js").write_text("needle", encoding="utf-8")
            (root / "main.py").write_text("needle = True", encoding="utf-8")
            with patch.object(tools, "WORKSPACE", root):
                result = tools.search_files("needle")
                self.assertEqual([row["path"] for row in result["matches"]], ["main.py"])

    def test_direct_access_to_git_metadata_and_dependency_trees_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git = root / ".git"
            deps = root / "node_modules"
            git.mkdir(); deps.mkdir()
            (git / "config").write_text("[remote]\nurl = https://example.com/private\n", encoding="utf-8")
            (deps / "package.json").write_text('{"name":"dep"}', encoding="utf-8")
            with patch.object(tools, "WORKSPACE", root):
                self.assertIn("error", tools.read_file(".git/config"))
                self.assertIn("error", tools.read_file("node_modules/package.json"))
                with self.assertRaisesRegex(ValueError, "excluded directory"):
                    tools.safe_path(".git/config")

    def test_inline_credentials_are_redacted_from_read_search_and_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample = root / "config.py"
            sample.write_text('API_KEY = "sk-' + 'A' * 32 + '"\nDB_URL = "postgres://alice:password123@localhost:5432/app"\n', encoding="utf-8")
            with patch.object(tools, "WORKSPACE", root):
                read_result = tools.read_file("config.py")
                search_result = tools.search_files("API_KEY")
                context = tools.build_context_pack("config", 5000)["context"]
            for output in (read_result["content"], search_result["matches"][0]["text"], context):
                self.assertNotIn("sk-" + "A" * 32, output)
                self.assertNotIn("password123", output)
                self.assertIn("[REDACTED", output)


class ApprovalConflictAndUndoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "workspace"
        self.root.mkdir()
        self.data = Path(self.temp.name) / "data"
        self.backups = Path(self.temp.name) / "backups"
        self.old_store = main_module.store
        self.old_safe_path = main_module.safe_path
        self.old_env = {key: os.environ.get(key) for key in ("INDRA_WORKSPACE", "INDRA_DATA_DIR", "INDRA_BACKUP_DIR")}
        os.environ["INDRA_WORKSPACE"] = str(self.root)
        os.environ["INDRA_DATA_DIR"] = str(self.data)
        os.environ["INDRA_BACKUP_DIR"] = str(self.backups)
        self.store = Store()
        main_module.store = self.store
        main_module.safe_path = lambda relative: (self.root / relative).resolve()
        self.client_cm = TestClient(main_module.app)
        self.client = self.client_cm.__enter__()

    def tearDown(self):
        self.client_cm.__exit__(None, None, None)
        main_module.store = self.old_store
        main_module.safe_path = self.old_safe_path
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.temp.cleanup()

    def _proposal(self, path, content, expected_exists, current_bytes=None):
        expected_hash = hashlib.sha256(current_bytes).hexdigest() if current_bytes is not None else None
        return self.store.add_action({
            "kind": "write_file", "path": path, "content": content, "reason": "test proposal",
            "overwrites_existing": expected_exists, "expected_exists": expected_exists,
            "expected_sha256": expected_hash,
        })

    def test_stale_overwrite_is_rejected_without_clobbering_newer_content(self):
        target = self.root / "note.md"
        target.write_text("original", encoding="utf-8")
        action = self._proposal("note.md", "agent version", True, b"original")
        target.write_text("user's newer edits", encoding="utf-8")
        response = self.client.post(f"/api/actions/{action['id']}", json={"decision": "approve"})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(target.read_text(encoding="utf-8"), "user's newer edits")
        self.assertEqual(next(a for a in self.store.list_actions() if a["id"] == action["id"])["status"], "conflict")

    def test_approved_overwrite_can_be_undone_from_verified_backup(self):
        target = self.root / "note.md"
        target.write_text("original", encoding="utf-8")
        action = self._proposal("note.md", "agent version", True, b"original")
        response = self.client.post(f"/api/actions/{action['id']}", json={"decision": "approve"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(target.read_text(encoding="utf-8"), "agent version")
        undo = self.client.post(f"/api/actions/{action['id']}/undo")
        self.assertEqual(undo.status_code, 200, undo.text)
        self.assertEqual(target.read_text(encoding="utf-8"), "original")

    def test_legacy_overwrite_without_target_hash_is_rejected(self):
        target = self.root / "note.md"
        target.write_text("keep me", encoding="utf-8")
        action = self.store.add_action({"kind": "write_file", "path": "note.md", "content": "replace me",
                                        "reason": "legacy proposal", "overwrites_existing": True,
                                        "expected_exists": True})
        response = self.client.post(f"/api/actions/{action['id']}", json={"decision": "approve"})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(target.read_text(encoding="utf-8"), "keep me")

    def test_target_changed_during_staging_is_rejected(self):
        target = self.root / "note.md"
        target.write_text("original", encoding="utf-8")
        action = self._proposal("note.md", "agent version", True, b"original")
        original_hash = main_module._sha256_file
        target_hash_calls = 0
        def racing_hash(path):
            nonlocal target_hash_calls
            result = original_hash(path)
            if Path(path) == target:
                target_hash_calls += 1
                if target_hash_calls == 3:
                    target.write_text("concurrent user edit", encoding="utf-8")
                    return original_hash(path)
            return result
        with patch.object(main_module, "_sha256_file", side_effect=racing_hash):
            response = self.client.post(f"/api/actions/{action['id']}", json={"decision": "approve"})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(target.read_text(encoding="utf-8"), "concurrent user edit")

    def test_undo_refuses_corrupted_backup(self):
        target = self.root / "note.md"
        target.write_text("original", encoding="utf-8")
        action = self._proposal("note.md", "agent version", True, b"original")
        apply = self.client.post(f"/api/actions/{action['id']}", json={"decision": "approve"})
        self.assertEqual(apply.status_code, 200, apply.text)
        stored = next(row for row in self.store.list_actions() if row["id"] == action["id"])
        Path(stored["backup_path"]).write_text("tampered backup", encoding="utf-8")
        undo = self.client.post(f"/api/actions/{action['id']}/undo")
        self.assertEqual(undo.status_code, 409, undo.text)
        self.assertEqual(target.read_text(encoding="utf-8"), "agent version")

    def test_undo_refuses_to_overwrite_changes_made_after_approval(self):
        target = self.root / "note.md"
        target.write_text("original", encoding="utf-8")
        action = self._proposal("note.md", "agent version", True, b"original")
        apply = self.client.post(f"/api/actions/{action['id']}", json={"decision": "approve"})
        self.assertEqual(apply.status_code, 200, apply.text)
        target.write_text("later human edit", encoding="utf-8")
        undo = self.client.post(f"/api/actions/{action['id']}/undo")
        self.assertEqual(undo.status_code, 409, undo.text)
        self.assertEqual(target.read_text(encoding="utf-8"), "later human edit")


class LocalSurfaceAndStoreTests(unittest.TestCase):
    def test_foreign_origin_and_non_loopback_host_are_rejected(self):
        with TestClient(main_module.app) as client:
            origin = client.get("/api/health", headers={"Origin": "https://attacker.example"})
            host = client.get("/api/health", headers={"Host": "attacker.example"})
        self.assertEqual(origin.status_code, 403)
        self.assertEqual(host.status_code, 421)

    def test_synthetic_testserver_host_is_not_accepted_in_normal_runtime(self):
        with patch.dict(os.environ, {"INDRA_REMOTE_ACCESS_ENABLED": "false"}):
            with TestClient(main_module.app, client=("127.0.0.1", 55123)) as client:
                response = client.get("/api/health", headers={"Host": "testserver"})
        self.assertEqual(response.status_code, 421)

    def test_tailscale_remote_mode_requires_login_and_same_origin(self):
        hostname = "my-pc.example-tailnet.ts.net"
        token = "ab" * 32
        with patch.dict(os.environ, {"INDRA_REMOTE_ACCESS_ENABLED": "true", "INDRA_REMOTE_ACCESS_TOKEN": token}):
            with TestClient(main_module.app, follow_redirects=False) as client:
                root = client.get("/", headers={"Host": hostname})
                locked = client.get("/api/health", headers={"Host": hostname, "Origin": "https://" + hostname})
                wrong_origin = client.get("/api/health", headers={"Host": hostname, "Origin": "https://attacker.example"})
                login = client.post("/remote/login", data={"token": token}, headers={"Host": hostname, "Origin": "https://" + hostname})
                cookie = login.cookies.get(main_module.REMOTE_COOKIE_NAME)
                unlocked = client.get("/api/health", headers={"Host": hostname, "Origin": "https://" + hostname, "Cookie": f"{main_module.REMOTE_COOKIE_NAME}={cookie}"})
                signed_out = client.get("/remote/logout", headers={"Host": hostname, "Cookie": f"{main_module.REMOTE_COOKIE_NAME}={cookie}"}, follow_redirects=False)
        self.assertEqual(root.status_code, 303)
        self.assertEqual(root.headers.get("location"), "/remote/login")
        self.assertEqual(locked.status_code, 401)
        self.assertEqual(wrong_origin.status_code, 403)
        self.assertEqual(login.status_code, 303)
        self.assertIn("httponly", login.headers.get("set-cookie", "").lower())
        self.assertIn("secure", login.headers.get("set-cookie", "").lower())
        self.assertIn("samesite=strict", login.headers.get("set-cookie", "").lower())
        self.assertEqual(unlocked.status_code, 200, unlocked.text)
        self.assertEqual(unlocked.headers.get("cache-control"), "no-store")
        self.assertEqual(unlocked.headers.get("strict-transport-security"), "max-age=31536000")
        self.assertEqual(unlocked.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(signed_out.status_code, 303)
        self.assertEqual(signed_out.headers.get("location"), "/remote/login")
        self.assertIn("max-age=0", signed_out.headers.get("set-cookie", "").lower())

    def test_remote_login_body_is_hard_capped_before_parsing(self):
        token = "ab" * 32
        hostname = "my-pc.example-tailnet.ts.net"
        with patch.dict(os.environ, {"INDRA_REMOTE_ACCESS_ENABLED": "true", "INDRA_REMOTE_ACCESS_TOKEN": token}):
            with TestClient(main_module.app, follow_redirects=False) as client:
                response = client.post("/remote/login", content=b"x" * 4097,
                                       headers={"Host": hostname, "Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.headers.get("cache-control"), "no-store")

    def test_tailscale_remote_mode_fails_closed_without_long_token(self):
        with patch.dict(os.environ, {"INDRA_REMOTE_ACCESS_ENABLED": "true", "INDRA_REMOTE_ACCESS_TOKEN": "short"}):
            with TestClient(main_module.app, follow_redirects=False) as client:
                response = client.get("/api/health", headers={"Host": "my-pc.example-tailnet.ts.net"})
                login = client.get("/remote/login", headers={"Host": "my-pc.example-tailnet.ts.net"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(login.status_code, 503)

    def test_remote_cookie_is_bound_to_host_and_expires(self):
        token = "ab" * 32
        now = 1_800_000_000
        cookie = main_module._remote_cookie(token, "pc.ts.net", issued_at=now)
        self.assertTrue(main_module._valid_remote_cookie(cookie, token, "pc.ts.net", now=now + 10))
        self.assertFalse(main_module._valid_remote_cookie(cookie, token, "other.ts.net", now=now + 10))
        self.assertFalse(main_module._valid_remote_cookie(cookie, token, "pc.ts.net", now=now + main_module.REMOTE_SESSION_TTL_SECONDS + 1))

    def test_sqlite_claim_is_single_winner_across_store_instances(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"INDRA_DATA_DIR": directory}):
            first, second = Store(), Store()
            action = first.add_action({"kind": "write_file", "path": "a.txt", "content": "hi"})
            claims = [first.claim_action(action["id"]), second.claim_action(action["id"])]
            self.assertEqual(sum(claim is not None for claim in claims), 1)

    def test_legacy_json_is_imported_once(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"INDRA_DATA_DIR": directory}):
            root = Path(directory)
            (root / "runs.json").write_text(json.dumps([{"run_id": "old-run", "status": "completed", "created_at": "2026-01-01T00:00:00+00:00"}]), encoding="utf-8")
            (root / "pending_actions.json").write_text(json.dumps([{"id": "old-action", "status": "pending", "created_at": "2026-01-01T00:00:00+00:00"}]), encoding="utf-8")
            store = Store()
            self.assertEqual(store.list_runs()[0]["run_id"], "old-run")
            self.assertEqual(store.list_actions()[0]["id"], "old-action")
            store2 = Store()
            self.assertEqual(len(store2.list_runs()), 1)


class ProviderStreamingTests(unittest.TestCase):
    def test_malformed_models_response_fails_with_actionable_provider_error(self):
        def handler(request):
            return httpx.Response(200, json=["not", "an", "object"])
        async def scenario():
            provider = OpenAICompatibleProvider()
            await provider.aclose()
            provider.base_url = "http://mock/v1"
            provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            try:
                with self.assertRaisesRegex(ProviderError, "invalid /models response"):
                    await provider.list_models(force=True)
            finally:
                await provider.aclose()
        asyncio.run(scenario())

    def test_streaming_tool_call_deltas_are_reconstructed(self):
        def handler(request):
            if request.url.path.endswith("/models"):
                return httpx.Response(200, json={"data": [{"id": "mock-model"}]})
            body = b"".join([
                b'data: {"choices":[{"delta":{"role":"assistant","content":"Checking "}}]}\n\n',
                b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"read_file","arguments":"{\\\"path\\\":"}}]}}]}\n\n',
                b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\\"README.md\\\"}"}}]}}]}\n\n',
                b'data: [DONE]\n\n',
            ])
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)

        async def scenario():
            provider = OpenAICompatibleProvider()
            await provider.aclose()
            provider.base_url = "http://mock/v1"
            provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            tokens = []
            try:
                result = await provider.chat_stream([{"role": "user", "content": "read README"}], tools=[{"type": "function", "function": {"name": "read_file", "parameters": {"type": "object"}}}], on_token=tokens.append)
                return result, tokens
            finally:
                await provider.aclose()
        result, tokens = asyncio.run(scenario())
        self.assertEqual("".join(tokens), "Checking ")
        self.assertEqual(result["tool_calls"][0]["function"]["name"], "read_file")
        self.assertEqual(json.loads(result["tool_calls"][0]["function"]["arguments"]), {"path": "README.md"})


if __name__ == "__main__":
    unittest.main()
