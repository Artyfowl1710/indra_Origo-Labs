import asyncio
import base64
import copy
import io
import json
import unittest
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, patch

import httpx
from PIL import Image

from origo_runtime.gateway import create_app
from origo_runtime.image_input import prepare_messages, validate_image
from origo_runtime.llamacpp import LlamaRuntime, MODELS

TOKEN = "test-token-only-" * 4


def image_url():
    data = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(data, format="PNG")
    return "data:image/png;base64," + base64.b64encode(data.getvalue()).decode()


class ImageBoundaryTests(unittest.TestCase):
    def test_rejects_remote_files_and_invalid_data(self):
        for url in ["http://localhost/secret", "file:///C:/secret", "data:image/png;base64,??",
                    "data:image/png;base64," + base64.b64encode(b"not an image").decode()]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_image(url)

    def test_mime_must_match_bytes(self):
        with self.assertRaises(ValueError):
            validate_image(image_url().replace("image/png", "image/jpeg"))

    def test_preparation_never_mutates_saved_messages(self):
        original = [{"role": "user", "content": [{"type": "text", "text": "Read this"},
                    {"type": "image_url", "image_url": {"url": image_url()}}]}]
        before = copy.deepcopy(original)
        prepared, images, question = prepare_messages(original)
        self.assertEqual(original, before)
        self.assertEqual(len(images), 1)
        self.assertEqual(question, "Read this")
        self.assertEqual(prepared[0]["content"], [{"type": "text", "text": "Read this"}])

    def test_tool_continuation_does_not_reparse_prior_image(self):
        rows = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_url()}}]},
                {"role": "assistant", "content": None}, {"role": "tool", "content": "done", "tool_call_id": "1"}]
        prepared, images, _ = prepare_messages(rows)
        self.assertEqual(images, [])
        self.assertIn("Earlier image", prepared[0]["content"][0]["text"])


class FakeRuntime:
    def __init__(self):
        self.route = self.active_device = None
        self.routes = []

    async def ensure(self, route):
        self.routes.append(route)
        self.route, self.active_device = route, "cpu"
        return "http://runtime"

    async def stop(self):
        self.route = None


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.runtime = FakeRuntime()
        self.calls = []

        async def handler(request):
            body = json.loads(request.content)
            self.calls.append(body)
            await asyncio.sleep(.01)
            if body["model"] == "origo-vision":
                return httpx.Response(200, json={"choices": [{"message": {"content": "INDRA42"}}]})
            if body.get("stream"):
                return httpx.Response(200, content=b'data: {"choices":[]}\n\ndata: [DONE]\n\n')
            return httpx.Response(200, json={"choices": [{"message": {"content": "Answer"}}]})

        app = create_app(self.runtime, TOKEN, transport=httpx.MockTransport(handler))
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://local",
                                        headers={"Authorization": "Bearer " + TOKEN})

    async def asyncTearDown(self):
        await self.client.aclose()

    def payload(self, image=False):
        content = [{"type": "text", "text": "Read the code"}]
        if image:
            content.append({"type": "image_url", "image_url": {"url": image_url()}})
        return {"model": "origo-auto", "messages": [{"role": "user", "content": content}]}

    async def test_authentication_and_browser_origin(self):
        self.assertEqual((await self.client.get("/health", headers={"Authorization": "Bearer wrong"})).status_code, 401)
        self.assertEqual((await self.client.get("/health", headers={"Origin": "https://evil.example"})).status_code, 403)

    async def test_invalid_json_and_contracts(self):
        self.assertEqual((await self.client.post("/v1/chat/completions", content="{")).status_code, 400)
        for payload in [[], {}, {"messages": [3]}, {**self.payload(), "stream": "yes"},
                        {**self.payload(), "max_tokens": 999999}, {**self.payload(True), "model": "origo-qwen35"}]:
            self.assertEqual((await self.client.post("/v1/chat/completions", json=payload)).status_code, 400)
        self.assertEqual(self.runtime.routes, [])

    async def test_catalog_lists_both_specialists_and_auto(self):
        response=await self.client.get("/v1/models")
        self.assertEqual({m["id"] for m in response.json()["data"]},{"origo-auto","origo-qwen35","origo-vision"})

    async def test_direct_ocr_never_switches_to_the_coding_model(self):
        payload={**self.payload(True),"model":"origo-vision"}
        response=await self.client.post("/v1/chat/completions",json=payload)
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.runtime.routes,["vision"])
        self.assertEqual((await self.client.get("/health")).json()["last_request"]["models"],["origo-vision"])
        self.assertEqual((await self.client.post("/v1/chat/completions",json={**self.payload(),"model":"origo-vision"})).status_code,400)

    async def test_automatic_image_routing_preserves_tools_and_messages(self):
        payload = self.payload(True)
        payload["tools"] = [{"type": "function", "function": {"name": "read_file"}}]
        before = copy.deepcopy(payload)
        response = await self.client.post("/v1/chat/completions", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.runtime.routes, ["vision", "text"])
        self.assertNotIn("tools", self.calls[0])
        self.assertEqual(self.calls[1]["tools"], payload["tools"])
        self.assertIn("INDRA42", self.calls[1]["messages"][-1]["content"])
        self.assertEqual(payload, before)
        health = (await self.client.get("/health")).json()
        self.assertEqual(health["last_request"]["route"], "vision→text")
        self.assertNotIn("INDRA42", json.dumps(health))

    async def test_concurrent_image_turns_hold_one_lease(self):
        responses = await asyncio.gather(*[
            self.client.post("/v1/chat/completions", json=self.payload(True)) for _ in range(2)])
        self.assertTrue(all(row.status_code == 200 for row in responses))
        self.assertEqual(self.runtime.routes, ["vision", "text", "vision", "text"])
        response = await self.client.post("/v1/chat/completions", json=self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.runtime.routes[-1], "text")
        self.assertEqual(len(self.calls[-1]["messages"][0]["content"]), 1)

    async def test_streaming_and_queue_release(self):
        response = await self.client.post("/v1/chat/completions", json={**self.payload(True), "stream": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-origo-route"], "vision-to-text")
        self.assertIn("[DONE]", response.text)
        self.assertEqual((await self.client.get("/health")).json()["pending"], 0)

    async def test_missing_runtime_returns_bounded_error_and_releases_lease(self):
        async def unavailable(route):
            raise FileNotFoundError("private file path")
        self.runtime.ensure = unavailable
        response = await self.client.post("/v1/chat/completions", json=self.payload())
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private file path", response.text)
        self.assertEqual((await self.client.get("/health")).json()["pending"], 0)

    async def test_cancelled_load_releases_lease_for_next_turn(self):
        entered, cancelled = asyncio.Event(), asyncio.Event()
        normal = self.runtime.ensure
        async def loading(route):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        self.runtime.ensure = loading
        task = asyncio.create_task(self.client.post("/v1/chat/completions", json=self.payload()))
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(cancelled.wait(), 2)
        self.assertEqual((await self.client.get("/health")).json()["pending"], 0)
        self.runtime.ensure = normal
        self.assertEqual((await self.client.post("/v1/chat/completions", json=self.payload())).status_code, 200)


class RuntimeLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_containment_assignment_failure_reaps_worker_before_health_probe(self):
        class Child:
            returncode = None
            terminated = False
            def terminate(child): child.terminated = True; child.returncode = 0
            async def wait(child): return child.returncode
        child = Child()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = LlamaRuntime(root, root, root, "cpu")
            with patch("origo_runtime.llamacpp.require_owned_process_tree"), \
                 patch("origo_runtime.llamacpp.contain_owned_child", side_effect=RuntimeError("fixture assignment denied")), \
                 patch("origo_runtime.llamacpp.asyncio.create_subprocess_exec", AsyncMock(return_value=child)), \
                 patch("origo_runtime.llamacpp.httpx.AsyncClient") as client:
                with self.assertRaises(RuntimeError):
                    await runtime._start("text", root / "fixture.gguf", "fixture", 16384, "cpu")
                client.assert_not_called()
            self.assertTrue(child.terminated)
            self.assertIsNone(runtime.process)

    async def test_job_creation_failure_does_not_spawn_a_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = LlamaRuntime(root, root, root, "cpu")
            with patch("origo_runtime.llamacpp.require_owned_process_tree", side_effect=RuntimeError("fixture job denied")), \
                 patch("origo_runtime.llamacpp.asyncio.create_subprocess_exec", AsyncMock()) as spawn:
                with self.assertRaises(RuntimeError):
                    await runtime._start("text", root / "fixture.gguf", "fixture", 16384, "cpu")
                spawn.assert_not_called()

    async def test_stop_tolerates_worker_exiting_before_terminate(self):
        class Child:
            returncode = None
            def terminate(child): raise ProcessLookupError()
            async def wait(child): child.returncode = 0; return 0
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = LlamaRuntime(root, root, root, "cpu")
            runtime.process, runtime.route, runtime.active_device = Child(), "text", "cpu"
            await runtime.stop()
            self.assertIsNone(runtime.process)
            self.assertIsNone(runtime.route)
            self.assertIsNone(runtime.active_device)

    async def test_auto_retries_cpu_before_any_output_on_gpu_startup_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / MODELS["text"][0]).touch()
            (root / "cuda_v13").mkdir()
            (root / "cuda_v13/ggml-cuda.dll").touch()
            runtime = LlamaRuntime(root, root, root, "auto")
            attempts = []
            async def verified():
                pass
            async def start(route, model, alias, context, device):
                attempts.append(device)
                if device == "gpu":
                    raise RuntimeError("No GPU available")
                runtime.origin, runtime.route, runtime.active_device = "http://cpu", route, device
            runtime.verify, runtime._start = verified, start
            self.assertEqual(await runtime.ensure("text"), "http://cpu")
            self.assertEqual(attempts, ["gpu", "cpu"])
            self.assertEqual(runtime.active_device, "cpu")

    async def test_missing_model_fails_before_process_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = LlamaRuntime(root, root, root, "cpu")
            with self.assertRaises(FileNotFoundError):
                await runtime.ensure("text")
            self.assertIsNone(runtime.process)


if __name__ == "__main__":
    unittest.main()
