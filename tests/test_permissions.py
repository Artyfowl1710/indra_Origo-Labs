from __future__ import annotations
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.agent import Agent
from app.permissions import PermissionBroker
from app.store import Store
from app.tools import available_tool_specs
import app.main as main_module


class PermissionBrokerTests(unittest.TestCase):
    def test_network_actions_wait_for_explicit_approval_and_redact_query_strings(self):
        async def scenario():
            broker = PermissionBroker("ask")
            events = []
            task = asyncio.create_task(broker.request("web_fetch", {"url": "https://example.org/docs?token=VERY_SECRET_TOKEN"}, events.append))
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            prompt = events[0]["permission"]
            self.assertEqual(prompt["host"], "example.org")
            self.assertNotIn("VERY_SECRET_TOKEN", prompt["detail"])
            decision = broker.decide(prompt["id"], "approve", "domain")
            self.assertEqual(decision["scope"], "domain")
            self.assertTrue(await task)
            # Grant is exact-host, in-memory only; a different host still waits.
            self.assertTrue(await broker.request("web_fetch", {"url": "https://example.org/next"}, events.append))
            other = asyncio.create_task(broker.request("web_fetch", {"url": "https://other.example/"}, events.append))
            await asyncio.sleep(0)
            self.assertFalse(other.done())
            pending = broker.pending()[0]
            broker.decide(pending["id"], "deny", "once")
            self.assertFalse(await other)
            broker.clear_session_grants()
            self.assertEqual(broker.snapshot()["session_allowed_domains"], [])
        asyncio.run(scenario())

    def test_network_deny_and_noninteractive_runs_fail_closed(self):
        async def scenario():
            events = []
            blocked = PermissionBroker("deny")
            self.assertFalse(await blocked.request("web_search", {"query": "query"}, events.append))
            self.assertEqual(events, [])
            ask = PermissionBroker("ask")
            self.assertFalse(await ask.request("web_search", {"query": "query"}, None))
            self.assertEqual(ask.pending(), [])
        asyncio.run(scenario())

    def test_plugin_and_docker_calls_require_approval_too(self):
        async def scenario():
            broker = PermissionBroker()
            for tool, args in [("plugin__notes__search", {"query": "x"}),
                               ("sandbox_run", {"command": ["python", "-V"]})]:
                events = []
                task = asyncio.create_task(broker.request(tool, args, events.append))
                await asyncio.sleep(0)
                self.assertFalse(task.done())
                row = events[0]["permission"]
                self.assertIn(row["kind"], {"plugin", "sandbox"})
                broker.decide(row["id"], "approve", "once")
                self.assertTrue(await task)
        asyncio.run(scenario())

    def test_networked_docker_run_explains_broad_egress_and_stays_one_shot(self):
        async def scenario():
            broker = PermissionBroker()
            events = []
            task = asyncio.create_task(broker.request(
                "sandbox_run", {"command": ["python", "-m", "pip", "install", "x"], "network_access": True}, events.append))
            await asyncio.sleep(0)
            prompt = events[0]["permission"]
            self.assertIn("general outbound bridge networking", prompt["summary"].lower())
            self.assertIn("not domain-filtered", prompt["detail"].lower())
            self.assertEqual(prompt["scope_options"], ["once"])
            broker.decide(prompt["id"], "deny", "once")
            self.assertFalse(await task)
        asyncio.run(scenario())

    def test_policy_change_during_request_assembly_fails_closed(self):
        async def scenario():
            broker = PermissionBroker("ask")
            original_build = broker._build_request
            def build_then_block(tool, args):
                row = original_build(tool, args)
                broker.set_network_policy("deny")
                return row
            broker._build_request = build_then_block
            emitted = []
            allowed = await broker.request("web_search", {"query": "example"}, event_sink=emitted.append)
            self.assertFalse(allowed)
            self.assertEqual(emitted, [])
            self.assertEqual(broker.pending(), [])
        asyncio.run(scenario())

    def test_revoking_network_policy_rejects_pending_approval(self):
        async def scenario():
            broker = PermissionBroker("ask")
            events = []
            task = asyncio.create_task(broker.request("web_fetch", {"url": "https://example.org/"}, events.append))
            await asyncio.sleep(0)
            self.assertEqual(len(broker.pending()), 1)
            broker.set_network_policy("deny")
            await asyncio.sleep(0)
            self.assertFalse(await task)
            self.assertEqual(broker.pending(), [])
        asyncio.run(scenario())

    def test_permission_queue_has_a_fixed_upper_bound(self):
        async def scenario():
            broker = PermissionBroker()
            events = []
            tasks = [asyncio.create_task(broker.request("web_search", {"query": f"query {i}"}, events.append)) for i in range(16)]
            await asyncio.sleep(0)
            self.assertEqual(len(broker.pending()), 16)
            self.assertFalse(await broker.request("web_search", {"query": "overflow"}, events.append))
            self.assertEqual(len(broker.pending()), 16)
            for event in events:
                broker.decide(event["permission"]["id"], "deny")
            self.assertTrue(all(result is False for result in await asyncio.gather(*tasks)))
        asyncio.run(scenario())

    def test_agent_web_tool_is_not_executed_when_permission_is_denied(self):
        class Model:
            model = _resolved_model = "test-model"
            def __init__(self): self.calls = 0
            async def chat(self, messages, tools):
                self.calls += 1
                if self.calls == 1:
                    names = {row["function"]["name"] for row in tools}
                    self_outer.assertIn("web_search", names)
                    return {"role": "assistant", "content": "", "tool_calls": [{
                        "id": "web1", "type": "function", "function": {"name": "web_search", "arguments": json.dumps({"query": "test query"})}}]}
                return {"role": "assistant", "content": "I did not access the web because permission was denied."}
        self_outer = self
        async def scenario():
            events = []
            async def deny(tool, args, event_sink, audit=None):
                events.append((tool, args))
                return False
            with patch("app.agent.execute", side_effect=AssertionError("network tool must not execute")):
                result = await Agent(Model(), Store()).run("search for something", event_sink=lambda e: None,
                                                          permission_requester=deny)
            self.assertEqual(events[0][0], "web_search")
            self.assertEqual(result["trace"][0]["category"], "permission_denied")
            self.assertIn("permission was denied", result["answer"])
        asyncio.run(scenario())

    def test_plan_mode_removes_write_plugin_and_sandbox_capabilities(self):
        class Model:
            model = _resolved_model = "test-model"
            def __init__(self): self.tool_names = set()
            async def chat(self, messages, tools):
                self.tool_names = {row["function"]["name"] for row in tools}
                return {"role": "assistant", "content": "Plan only."}
        async def scenario():
            model = Model()
            result = await Agent(model, Store()).run("Review and plan", mode="plan")
            self.assertEqual(result["mode"], "plan")
            self.assertIn("read_file", model.tool_names)
            self.assertNotIn("propose_write", model.tool_names)
            self.assertNotIn("sandbox_run", model.tool_names)
            self.assertFalse(any(x.startswith("plugin__") for x in model.tool_names))
            self.assertNotIn("web_search", model.tool_names) if os.getenv("INDRA_WEB_TOOLS_ENABLED", "true").lower() not in {"1", "true", "yes", "on"} else None
        asyncio.run(scenario())

    def test_policy_api_defaults_to_ask_and_supports_blocking(self):
        original_broker = main_module.permission_broker
        old_store = main_module.store
        temp = tempfile.TemporaryDirectory()
        try:
            with patch.dict(os.environ, {"INDRA_DATA_DIR": str(Path(temp.name) / "data")}):
                main_module.store = Store()
                main_module.permission_broker = PermissionBroker("ask")
                with TestClient(main_module.app) as client:
                    before = client.get("/api/policy")
                    self.assertEqual(before.status_code, 200)
                    self.assertEqual(before.json()["network_policy"], "ask")
                    response = client.post("/api/policy", json={"network_policy": "deny", "clear_session_grants": True})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()["network_policy"], "deny")
                    invalid = client.post("/api/policy", json={"network_policy": "allow-all"})
                    self.assertEqual(invalid.status_code, 422)
        finally:
            main_module.permission_broker = original_broker
            main_module.store = old_store
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
