import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

import app.knowledge as knowledge
import app.main as main_module
import app.tools as tools
from app.store import Store


class WorkspaceSearchProductTests(unittest.TestCase):
    def test_api_search_returns_safe_matches_and_skips_secrets_and_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "src" / "demo.py").write_text("value = 'needle'\n", encoding="utf-8")
            (root / ".env").write_text("TOKEN=needle-secret", encoding="utf-8")
            dep = root / "node_modules" / "pkg"
            dep.mkdir(parents=True)
            (dep / "dependency.js").write_text("needle in package", encoding="utf-8")
            previous = tools.WORKSPACE
            tools.WORKSPACE = root
            try:
                with TestClient(main_module.app) as client:
                    response = client.get("/api/workspace/search", params={"q": "needle"})
                    blank = client.get("/api/workspace/search", params={"q": "   "})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual([row["path"] for row in response.json()["matches"]], ["src/demo.py"])
                self.assertEqual(blank.status_code, 422)
            finally:
                tools.WORKSPACE = previous

    def test_symlink_file_is_blocked_when_platform_allows_symlink_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            root.mkdir()
            outside = Path(temp) / "outside.md"
            outside.write_text("do not read", encoding="utf-8")
            link = root / "linked.md"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation requires OS permission not available in this environment")
            previous = tools.WORKSPACE
            tools.WORKSPACE = root
            try:
                with self.assertRaisesRegex(ValueError, "Symlink"):
                    tools.safe_path("linked.md")
                self.assertNotIn("linked.md", [row["path"] for row in tools.workspace_inventory()])
            finally:
                tools.WORKSPACE = previous

    def test_knowledge_limit_rejects_float_and_boolean(self):
        for value in (3.0, True, 0, 9):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    tools.validate_tool_arguments("search_knowledge_base", {"query": "x", "limit": value})
        self.assertEqual(tools.validate_tool_arguments("search_knowledge_base", {"query": "x", "limit": 3})["limit"], 3)


class KnowledgeRetrievalTests(unittest.TestCase):
    def test_optional_qdrant_search_uses_embedding_and_read_only_query_endpoints(self):
        requests = []
        class Response:
            def __init__(self, code, body): self.status_code, self._body = code, body
            def json(self): return self._body
        class Client:
            def __init__(self, *a, **kw): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def post(self, url, headers=None, json=None):
                requests.append((url, headers or {}, json or {}))
                if url.endswith("/embeddings"):
                    return Response(200, {"data": [{"embedding": [0.1, 0.2, 0.3]}]})
                return Response(200, {"result": {"points": [{"id": "p1", "score": 0.91, "payload": {"text": "A retrieved note", "source": "notes.md"}}]}})
        env = {"QDRANT_COLLECTION": "research_notes", "QDRANT_URL": "http://127.0.0.1:6333",
               "EMBEDDING_MODEL": "e5-small", "EMBEDDING_BASE_URL": "http://127.0.0.1:8100/v1",
               "EMBEDDING_API_KEY": "local"}
        with patch.dict(os.environ, env, clear=False), patch("app.knowledge.httpx.Client", Client):
            result = knowledge.search_knowledge_base("retrieve a paper", limit=2)
        self.assertTrue(result["read_only"])
        self.assertEqual(result["results"][0]["text"], "A retrieved note")
        self.assertTrue(requests[0][0].endswith("/v1/embeddings"))
        self.assertTrue(requests[1][0].endswith("/collections/research_notes/points/query"))
        self.assertFalse(any(any(word in request[0].lower() for word in ("upsert", "delete", "batch")) for request in requests))

    def test_knowledge_status_redacts_credentials_from_endpoint(self):
        with patch.dict(os.environ, {"QDRANT_COLLECTION": "docs", "EMBEDDING_MODEL": "embed",
                                    "EMBEDDING_BASE_URL": "http://user:secret@127.0.0.1:9999/v1",
                                    "QDRANT_URL": "http://127.0.0.1:6333"}, clear=False):
            with TestClient(main_module.app) as client:
                data = client.get("/api/knowledge/status").json()
        self.assertTrue(data["enabled"])
        self.assertNotIn("secret", data["embedding_endpoint"])
        self.assertTrue(data["read_only"])


class ModelSmokeTests(unittest.TestCase):
    def setUp(self):
        self.old_active = main_module.run_slots.active
        main_module.run_slots.active = 0

    def tearDown(self):
        main_module.run_slots.active = self.old_active

    def test_smoke_probe_records_tool_call_without_executing_it(self):
        fake = AsyncMock(return_value={"content": None, "tool_calls": [{"function": {"name": "indra_harness_probe", "arguments": '{"status":"ok"}'}}]})
        with patch.object(main_module.provider, "chat", fake), TestClient(main_module.app) as client:
            response = client.post("/api/model/smoke", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "passed")
        self.assertTrue(response.json()["tool_calling_detected"])
        self.assertEqual(fake.await_count, 1)

    def test_smoke_probe_distinguishes_text_only_models(self):
        fake = AsyncMock(return_value={"content": "I cannot call functions here.", "tool_calls": []})
        with patch.object(main_module.provider, "chat", fake), TestClient(main_module.app) as client:
            response = client.post("/api/model/smoke", json={})
        self.assertEqual(response.json()["status"], "partial")
        self.assertTrue(response.json()["text_generation_ok"])
        self.assertFalse(response.json()["tool_calling_detected"])

    def test_smoke_probe_respects_run_admission_limit(self):
        main_module.run_slots.active = main_module.run_slots.capacity
        with TestClient(main_module.app) as client:
            response = client.post("/api/model/smoke", json={})
        self.assertEqual(response.status_code, 429)


class SandboxProposalApiTests(unittest.TestCase):
    def test_sandbox_changes_become_proposals_only_and_cannot_be_replayed(self):
        import app.tools as tool_module
        from app.sandbox import _remember_result_files
        old_store = main_module.store
        with tempfile.TemporaryDirectory() as temp:
            data_root = Path(temp) / "data"
            workspace = Path(temp) / "workspace"
            workspace.mkdir()
            run_id = "b" * 12
            _remember_result_files(run_id, workspace, {"new_module.py": "print('from sandbox')\n"})
            try:
                with patch.dict(os.environ, {"INDRA_DATA_DIR": str(data_root)}), patch.object(tool_module, "WORKSPACE", workspace):
                    main_module.store = Store()
                    with TestClient(main_module.app) as client:
                        response = client.post("/api/sandbox/propose-changes", json={"sandbox_run_id": run_id, "paths": ["new_module.py"]})
                        self.assertEqual(response.status_code, 200, response.text)
                        payload = response.json()
                        self.assertEqual(payload["status"], "approval_required")
                        self.assertEqual(len(payload["proposals"]), 1)
                        self.assertFalse((workspace / "new_module.py").exists())
                        actions = client.get("/api/actions").json()
                        self.assertTrue(any(row.get("path") == "new_module.py" and row.get("status") == "pending" for row in actions))
                        replay = client.post("/api/sandbox/propose-changes", json={"sandbox_run_id": run_id, "paths": ["new_module.py"]})
                        self.assertEqual(replay.status_code, 404)
                        self.assertFalse((workspace / "new_module.py").exists())
            finally:
                main_module.store = old_store


if __name__ == "__main__":
    unittest.main()

class TaskGraphApiTests(unittest.TestCase):
    def test_task_graph_api_rejects_cycles_before_model_use(self):
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as client:
            response = client.post('/api/task-graph', json={'tasks': [
                {'id': 'a', 'task': 'Inspect A', 'depends_on': ['b']},
                {'id': 'b', 'task': 'Inspect B', 'depends_on': ['a']}], 'max_concurrency': 2})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn('dependency cycle', response.json()['detail'])

    def test_task_graph_api_returns_run_id_and_persists_summary(self):
        from fastapi.testclient import TestClient
        from unittest.mock import AsyncMock, patch
        from app.main import app
        result = {'task_graph': True, 'task_count': 1, 'max_concurrency': 1, 'completed': 1,
                  'failed_or_skipped': 0, 'results': [{'id': 'a', 'status': 'completed', 'answer': 'done'}]}
        with patch('app.main.agent._run_task_graph', new_callable=AsyncMock, return_value=result):
            with TestClient(app) as client:
                response = client.post('/api/task-graph', json={'tasks': [{'id': 'a', 'task': 'Check the test setup'}], 'max_concurrency': 1})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['completed'], 1)
        self.assertRegex(data['graph_run_id'], r'^[0-9a-f]{32}$')

class SandboxImageBuildApiTests(unittest.TestCase):
    def test_image_build_requires_explicit_confirmation(self):
        with patch('app.main.sandbox.build_dev_image_after_explicit_confirmation') as build:
            with TestClient(main_module.app) as client:
                response = client.post('/api/sandbox/build-image', json={'confirmed': False})
        self.assertEqual(response.status_code, 400, response.text)
        build.assert_not_called()

    def test_confirmed_image_build_persists_selected_local_image(self):
        old_store = main_module.store
        old_active = main_module.run_slots.active
        old_override = main_module.sandbox._image_override
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {'INDRA_DATA_DIR': str(Path(temp) / 'data')}, clear=False):
                main_module.store = Store()
                main_module.run_slots.active = 0
                with patch('app.main.sandbox.build_dev_image_after_explicit_confirmation',
                           return_value={'status': 'built', 'image': 'indra-sandbox:dev', 'output': 'mock build'}):
                    try:
                        with TestClient(main_module.app) as client:
                            response = client.post('/api/sandbox/build-image', json={'confirmed': True})
                        self.assertEqual(response.status_code, 200, response.text)
                        self.assertEqual(response.json()['image'], 'indra-sandbox:dev')
                        self.assertEqual(main_module.store.get_setting('sandbox_image'), 'indra-sandbox:dev')
                        self.assertEqual(main_module.sandbox._configured_image(), 'indra-sandbox:dev')
                    finally:
                        main_module.store = old_store
                        main_module.run_slots.active = old_active
                        main_module.sandbox.set_image_override(old_override)

    def test_reset_image_policy_restores_env_default_and_persists_reset(self):
        old_store = main_module.store
        old_active = main_module.run_slots.active
        old_override = main_module.sandbox._image_override
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            'INDRA_DATA_DIR': str(Path(temp) / 'data'), 'INDRA_SANDBOX_IMAGE': 'python:3.12-slim'
        }, clear=False):
            main_module.store = Store()
            main_module.run_slots.active = 0
            main_module.sandbox.set_image_override('indra-sandbox:dev')
            main_module.store.set_setting('sandbox_image', 'indra-sandbox:dev')
            try:
                with TestClient(main_module.app) as client:
                    response = client.post('/api/policy', json={'reset_sandbox_image': True})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(response.json()['changed']['sandbox_image_reset'])
                self.assertIsNone(main_module.store.get_setting('sandbox_image'))
                self.assertEqual(main_module.sandbox._configured_image(), 'python:3.12-slim')
            finally:
                main_module.store = old_store
                main_module.run_slots.active = old_active
                main_module.sandbox.set_image_override(old_override)
