from __future__ import annotations
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agent import Agent
from app.sandbox import _resource_limits, _safe_copy_workspace, build_dev_image_after_explicit_confirmation, claim_cached_result_files, get_cached_result_files, network_mode_argument, run_sandboxed, status, _remember_result_files
from app.store import Store
from app.tools import available_tool_specs


class _ParallelModel:
    model = "test-model"
    _resolved_model = "test-model"
    async def chat(self, messages, tools):
        has_tool_result = any(row.get("role") == "tool" for row in messages)
        last_user = next((row.get("content", "") for row in reversed(messages) if row.get("role") == "user"), "")
        if "dispatch two child tasks" in last_user and not has_tool_result:
            return {"role": "assistant", "content": "", "tool_calls": [{
                "id": "call_parallel", "type": "function", "function": {"name": "parallel_tasks", "arguments": json.dumps({
                    "tasks": [{"id": "docs", "task": "Summarize project docs"}, {"id": "tests", "task": "Summarize test coverage"}]})}}]}
        return {"role": "assistant", "content": "Child or synthesis answer."}


class ParallelAgentTests(unittest.TestCase):
    def test_child_tool_surface_excludes_plugins_sandbox_and_delegation(self):
        safe = {"list_files", "read_file", "search_files", "build_context_pack",
                "search_knowledge_base", "web_search", "web_fetch", "web_research", "web_crawl", "load_skill"}
        names = {row["function"]["name"] for row in available_tool_specs(include_parallel=False, allowed_tool_names=safe)}
        self.assertIn("read_file", names)
        self.assertNotIn("propose_write", names)
        self.assertNotIn("sandbox_run", names)
        self.assertNotIn("parallel_tasks", names)
        self.assertNotIn("task_graph", names)
        self.assertFalse(any(name.startswith("plugin__") for name in names))

    def test_parallel_tool_runs_bounded_read_only_child_agents(self):
        store = Store()
        model = _ParallelModel()
        result = asyncio.run(Agent(model, store).run("dispatch two child tasks"))
        self.assertEqual(result["status"], "completed")
        parallel_trace = next(row for row in result["trace"] if row["tool"] == "parallel_tasks")
        detail = parallel_trace["result"]
        self.assertEqual(detail["task_count"], 2)
        self.assertLessEqual(detail["max_concurrency"], 3)
        self.assertTrue(all(row["status"] == "completed" for row in detail["results"]))
        self.assertTrue(all(row["run_id"] for row in detail["results"]))
        self.assertNotIn("propose_write", {row["function"]["name"] for row in available_tool_specs(include_parallel=False, allowed_tool_names={"list_files", "read_file", "search_files", "build_context_pack", "web_search", "web_fetch", "load_skill"})})

    def test_task_graph_runs_independent_nodes_in_parallel_and_dependencies_in_order(self):
        agent = Agent(_ParallelModel(), Store())
        active = 0
        max_active = 0
        contexts = {}
        async def fake_run(self, task, history=None, event_sink=None, stream=False, context=None, skills=None,
                           allow_parallel=True, allowed_tool_names=None, duration_cap_seconds=None):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            contexts[task] = context or ""
            await asyncio.sleep(0.01)
            active -= 1
            return {"status": "completed", "run_id": task.replace(" ", "-"), "duration_ms": 10,
                    "tool_calls": 0, "answer": f"answer for {task}"}
        graph = {"max_concurrency": 2, "tasks": [
            {"id": "a", "task": "Task A"}, {"id": "b", "task": "Task B"},
            {"id": "c", "task": "Task C", "depends_on": ["a", "b"]}]}
        with patch.object(Agent, "run", fake_run):
            result = asyncio.run(agent._run_task_graph(graph, "seed context", [], lambda *args, **kwargs: None))
        self.assertEqual(result["completed"], 3)
        self.assertEqual(result["task_count"], 3)
        self.assertLessEqual(max_active, 2)
        self.assertIn("answer for Task A", contexts["Task C"])
        self.assertIn("answer for Task B", contexts["Task C"])
        self.assertIn("UNTRUSTED DEPENDENCY RESULTS", contexts["Task C"])

    def test_task_graph_rejects_cycles_before_starting_child_runs(self):
        agent = Agent(_ParallelModel(), Store())
        graph = {"tasks": [
            {"id": "a", "task": "Task A", "depends_on": ["b"]},
            {"id": "b", "task": "Task B", "depends_on": ["a"]}]}
        with patch.object(Agent, "run", side_effect=AssertionError("no task should start")):
            result = asyncio.run(agent._run_task_graph(graph, "", [], lambda *args, **kwargs: None))
        self.assertIn("dependency cycle", result["error"])

    def test_parallel_tasks_reject_duplicates_and_invalid_payload(self):
        class Noop:
            model = "m"; _resolved_model = "m"
            async def chat(self, messages, tools):
                return {"role": "assistant", "content": "done"}
        agent = Agent(Noop(), Store())
        events = []
        result = asyncio.run(agent._run_parallel_tasks({"tasks": [{"id": "same", "task": "A"}, {"id": "same", "task": "B"}]}, "", [], events.append))
        self.assertIn("error", result)
        result = asyncio.run(agent._run_parallel_tasks({"tasks": []}, "", [], events.append))
        self.assertIn("error", result)


class SandboxTests(unittest.TestCase):
    def test_result_collection_reads_live_tmpfs_and_rejects_traversal_and_links(self):
        import io
        import subprocess
        import tarfile
        from app.sandbox import _collect_snapshot
        for name, kind, expected in [('nested/report.txt', 'file', 0), ('../escape.txt', 'file', 1), ('link', 'symlink', 1)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                def execute(args, **kwargs):
                    with tarfile.open(fileobj=kwargs['stdout'], mode='w') as bundle:
                        info = tarfile.TarInfo(name)
                        if kind == 'symlink':
                            info.type = tarfile.SYMTYPE
                            info.linkname = '/etc/passwd'
                            bundle.addfile(info)
                        else:
                            info.size = 6
                            bundle.addfile(info, io.BytesIO(b'result'))
                    return subprocess.CompletedProcess(args, 0, b'', b'')
                with patch('app.sandbox.subprocess.run', side_effect=execute):
                    result = _collect_snapshot('docker', 'fixture', Path(temp))
                self.assertEqual(result.returncode, expected)
                if expected == 0:
                    self.assertEqual((Path(temp) / name).read_bytes(), b'result')
                else:
                    self.assertEqual(list(Path(temp).iterdir()), [])

    def test_snapshot_streams_regular_files_into_container_without_host_mount(self):
        import subprocess
        import tarfile
        from app.sandbox import _stage_snapshot
        captured = {}
        def execute(args, **kwargs):
            captured['args'] = args
            with tarfile.open(fileobj=kwargs['stdin'], mode='r:') as bundle:
                captured['files'] = {row.name: bundle.extractfile(row).read() for row in bundle}
                self.assertTrue(all(row.isfile() for row in bundle.getmembers()))
            return subprocess.CompletedProcess(args, 0, b'', b'')
        with patch('app.sandbox.subprocess.run', side_effect=execute):
            result = _stage_snapshot('docker', 'scoped-fixture', {'nested/source.txt': b'sanitized text'})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(captured['files'], {'nested/source.txt': b'sanitized text'})
        self.assertEqual(captured['args'], ['docker', 'exec', '-i', '--user', '0', 'scoped-fixture', 'tar', '-xf', '-', '-C', '/workspace'])

    def test_dev_image_build_requires_confirmation_and_uses_only_docker_context(self):
        import subprocess
        with patch("app.sandbox.docker_binary", return_value="/usr/bin/docker") as docker, \
             patch("app.sandbox._run_small", return_value=subprocess.CompletedProcess(["docker", "info"], 0, b"27.0", b"")), \
             patch("app.sandbox.subprocess.run", return_value=subprocess.CompletedProcess(["docker", "build"], 0, b"built", b"")) as build:
            denied = build_dev_image_after_explicit_confirmation(False)
            self.assertIn("Explicit confirmation", denied["error"])
            docker.assert_not_called()
            result = build_dev_image_after_explicit_confirmation(True)
        self.assertEqual(result["status"], "built")
        self.assertEqual(result["image"], "indra-sandbox:dev")
        self.assertFalse(result["host_workspace_in_build_context"])
        args = build.call_args.args[0]
        self.assertEqual(args[1:2], ["build"])
        self.assertIn("--pull", args)
        self.assertEqual(args[-1], ".")
        self.assertEqual(Path(build.call_args.kwargs["cwd"]), Path(__file__).resolve().parents[1] / "docker")
        self.assertNotIn(".env", args)

    def test_sandbox_image_override_can_reset_to_environment_default(self):
        from app import sandbox as sandbox_module
        with patch.dict(os.environ, {"INDRA_SANDBOX_IMAGE": "python:3.12-slim"}):
            sandbox_module.set_image_override("indra-sandbox:dev")
            self.assertEqual(sandbox_module.status()["image"], "indra-sandbox:dev")
            sandbox_module.set_image_override(None)
            self.assertEqual(sandbox_module.status()["image"], "python:3.12-slim")

    def test_sandbox_disabled_by_default_and_tool_hidden(self):
        with patch.dict(os.environ, {"INDRA_ENABLE_DOCKER_SANDBOX": "false"}):
            self.assertFalse(status()["ready"])
            self.assertNotIn("sandbox_run", {row["function"]["name"] for row in available_tool_specs()})
            self.assertIn("disabled", run_sandboxed(["python", "--version"])["error"].lower())

    def test_sandbox_never_falls_back_to_host_when_docker_missing(self):
        with patch.dict(os.environ, {"INDRA_ENABLE_DOCKER_SANDBOX": "true"}), patch("app.sandbox.docker_binary", return_value=None):
            result = run_sandboxed(["python", "-V"])
            self.assertIn("Docker CLI was not found", result["error"])

    def test_sandbox_rejects_shell_string_and_bad_arguments(self):
        with patch.dict(os.environ, {"INDRA_ENABLE_DOCKER_SANDBOX": "true"}), patch("app.sandbox.docker_binary", return_value="/usr/bin/docker"):
            self.assertIn("argv array", run_sandboxed("python -V")["error"])
            self.assertIn("non-empty string", run_sandboxed(["python", ""]).get("error", ""))


    def test_sandbox_stages_only_safe_text_and_redacts_inline_credentials(self):
        from app import tools as tool_module
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            stage = Path(temp) / "stage"
            root.mkdir(); stage.mkdir()
            (root / "guide.md").write_text('API_KEY="SuperSecretValue123456"\nUseful content\n', encoding="utf-8")
            (root / ".env").write_text("PASSWORD=really-secret", encoding="utf-8")
            (root / "weights.gguf").write_bytes(b"binary model payload")
            (root / "history.sqlite3").write_bytes(b"database")
            (root / "credentials").mkdir()
            (root / "credentials" / "notes.md").write_text("private", encoding="utf-8")
            with patch.object(tool_module, "WORKSPACE", root):
                before, files, byte_count = _safe_copy_workspace(root, stage)
            self.assertEqual(files, 1)
            self.assertEqual(set(before), {"guide.md"})
            self.assertIn(b"[REDACTED]", before["guide.md"])
            self.assertNotIn(b"SuperSecretValue123456", before["guide.md"])
            self.assertFalse((stage / ".env").exists())
            self.assertFalse((stage / "weights.gguf").exists())
            self.assertFalse((stage / "history.sqlite3").exists())
            self.assertFalse((stage / "credentials" / "notes.md").exists())

    def test_network_mode_is_explicit_and_fails_closed_for_non_boolean_values(self):
        self.assertEqual(network_mode_argument(False), "--network=none")
        self.assertEqual(network_mode_argument(True), "--network=bridge")
        with self.assertRaises(ValueError):
            network_mode_argument("true")
        with self.assertRaises(ValueError):
            network_mode_argument(1)

    def test_sandbox_result_cache_is_workspace_scoped_and_one_time_claimed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            root.mkdir()
            run_id = "a" * 12
            _remember_result_files(run_id, root, {"main.py": "print('safe')\n", "README.md": "summary\n"})
            self.assertEqual(set(get_cached_result_files(run_id, root) or {}), {"main.py", "README.md"})
            claimed = claim_cached_result_files(run_id, root, ["main.py"])
            self.assertEqual(claimed, {"main.py": "print('safe')\n"})
            self.assertEqual(set(get_cached_result_files(run_id, root) or {}), {"README.md"})
            other = Path(temp) / "other"
            other.mkdir()
            self.assertIsNone(claim_cached_result_files(run_id, other, ["README.md"]))
            self.assertIsNone(claim_cached_result_files(run_id, root, ["main.py"]))

    def test_sandbox_resource_settings_are_hard_bounded(self):
        with patch.dict(os.environ, {
            "INDRA_SANDBOX_MEMORY_MB": "99999",
            "INDRA_SANDBOX_CPUS": "99",
            "INDRA_SANDBOX_PIDS": "1",
            "INDRA_SANDBOX_WORKSPACE_TMPFS_MB": "99999",
        }):
            limits = _resource_limits()
        self.assertEqual(limits["memory_mb"], 4096)
        self.assertEqual(limits["cpus"], 4.0)
        self.assertEqual(limits["pids"], 64)
        self.assertEqual(limits["workspace_tmpfs_mb"], 512)
        self.assertEqual(limits["workspace_tmpfs_bytes"], 512 * 1024 * 1024)

    def test_sandbox_status_explicitly_reports_network_and_copy_isolation(self):
        row = status()
        self.assertIn("none by default", row["network"])
        self.assertIn("not domain-filtered", row["network"])
        self.assertIn("no automatic write-back", row["workspace_mode"])
