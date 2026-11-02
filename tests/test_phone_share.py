import asyncio
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from origo_runtime.phone_config import save_settings
from origo_runtime.phone_share import owns_foreground_route, serve

ENDPOINT = "https://origo.private-fixture.ts.net"
ORIGIN = "http://127.0.0.1:8766"


def route():
    return {"Foreground": {"fixture-session": {"TCP": {"443": {"HTTPS": True}},
            "Web": {"origo.private-fixture.ts.net:443": {"Handlers": {"/": {"Proxy": ORIGIN}}}}}}}


class RouteOwnershipTests(unittest.TestCase):
    def test_accepts_only_exact_foreground_backend(self):
        self.assertTrue(owns_foreground_route(route(), ENDPOINT, ORIGIN))
        value = route()
        value["Foreground"]["fixture-session"]["Web"]["origo.private-fixture.ts.net:443"]["Handlers"]["/"]["Proxy"] += "/"
        self.assertTrue(owns_foreground_route(value, ENDPOINT, ORIGIN))
        self.assertFalse(owns_foreground_route(route(), ENDPOINT, "http://127.0.0.1:9999"))
        self.assertFalse(owns_foreground_route(route(), "https://other.private-fixture.ts.net", ORIGIN))

    def test_rejects_persistent_routes_funnel_other_services_and_extra_handlers(self):
        values = [{}, [], {"TCP": {"443": {"HTTPS": True}}}]
        for key in ("AllowFunnel", "Services", "Web", "TCP"):
            values.append({**route(), key: {"unexpected": True}})
        value = route()
        value["Foreground"]["other-session"] = copy.deepcopy(value["Foreground"]["fixture-session"])
        values.append(value)
        value = route()
        value["Foreground"]["fixture-session"]["Web"]["origo.private-fixture.ts.net:443"]["Handlers"]["/other"] = {"Text": "foreign"}
        values.append(value)
        for value in values:
            with self.subTest(value=value):
                self.assertFalse(owns_foreground_route(value, ENDPOINT, ORIGIN))


@unittest.skipUnless(os.name == "nt", "Windows signed-runtime supervisor")
class ShareLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.programs = self.home / "programs"
        (self.programs / "Tailscale").mkdir(parents=True)
        (self.programs / "Tailscale/tailscale.exe").touch()
        save_settings(self.home, {"endpoint": ENDPOINT, "username": "origo",
                                 "password": "fixture-password-123", "port": 8766})
        self.alive = True
        outer = self
        class Owner:
            def create_time(self): return 1
            def is_running(self): return outer.alive
            def cmdline(self): return ["python.exe", "-m", "hermes_cli.main", "dashboard", "--port", "8766"]
        self.owner = Owner()
        self.waiter = asyncio.Event()
        class Child:
            returncode = None
            def terminate(child): child.returncode = 0; outer.waiter.set()
            def kill(child): child.returncode = -1; outer.waiter.set()
            async def wait(child): await outer.waiter.wait(); return child.returncode
        self.child = Child()
        self.commands = []
        self.config = {}
        self.emitted = []
        self.http_status = 401
        async def command(executable, *args, **kwargs):
            self.commands.append(args)
            if args[0] == "status":
                return json.dumps({"BackendState": "Running", "Self": {"DNSName": "origo.private-fixture.ts.net."}}).encode()
            return json.dumps(self.config).encode()
        async def spawn(*args, **kwargs):
            self.spawn_args = args
            self.config = route()
            return self.child
        actual_client = httpx.AsyncClient
        async def handle(request):
            self.assertEqual(request.headers["host"], "origo.private-fixture.ts.net")
            return httpx.Response(self.http_status)
        def client(**kwargs): return actual_client(transport=httpx.MockTransport(handle), **kwargs)
        self.spawn_mock = AsyncMock(side_effect=spawn)
        for target, value in [
            ("origo_runtime.phone_share.command", command),
            ("origo_runtime.phone_share.verify_tailscale", AsyncMock()),
            ("origo_runtime.phone_share.require_owned_process_tree", lambda: None),
            ("origo_runtime.phone_share.contain_owned_child", lambda child: None),
            ("origo_runtime.phone_share.psutil.Process", lambda pid: self.owner),
            ("origo_runtime.phone_share.asyncio.create_subprocess_exec", self.spawn_mock),
            ("origo_runtime.phone_share.httpx.AsyncClient", client),
            ("origo_runtime.phone_share.emit", lambda state, message: self.emitted.append(state)),
        ]:
            context = patch(target, value); context.start(); self.addCleanup(context.stop)
        context = patch.dict(os.environ, {"ProgramFiles": str(self.programs)})
        context.start(); self.addCleanup(context.stop)

    async def test_never_overwrites_existing_serve_configuration(self):
        self.config = {"TCP": {"443": {"HTTPS": True}}}
        await serve(self.home, 8766, 1, 2)
        self.assertIn("conflict", self.emitted)
        self.spawn_mock.assert_not_called()

    async def test_refuses_ungated_backend_before_exposure(self):
        self.http_status = 200
        with self.assertRaises(RuntimeError):
            await serve(self.home, 8766, 1, 2)
        self.spawn_mock.assert_not_called()

    async def test_assignment_failure_stops_worker_without_confirming_sharing(self):
        with patch("origo_runtime.phone_share.contain_owned_child", side_effect=RuntimeError("fixture containment denied")):
            with self.assertRaises(RuntimeError):
                await serve(self.home, 8766, 1, 2)
        self.assertIsNotNone(self.child.returncode)
        self.assertNotIn("sharing", self.emitted)

    async def test_owner_loss_stops_only_owned_foreground_process(self):
        def emit(state, message):
            self.emitted.append(state)
            if state == "sharing": self.alive = False
        with patch("origo_runtime.phone_share.emit", emit):
            await asyncio.wait_for(serve(self.home, 8766, 1, 2), 3)
        self.assertEqual(self.spawn_args[1:], ("serve", "--https=443", ORIGIN))
        self.assertIsNotNone(self.child.returncode)
        self.assertIn("stopped", self.emitted)
        self.assertTrue(all("reset" not in command and "off" not in command and "funnel" not in command for command in self.commands))

    async def test_cancellation_cleans_up_foreground_session(self):
        task = None
        def emit(state, message):
            if state == "sharing": asyncio.get_running_loop().call_soon(task.cancel)
        with patch("origo_runtime.phone_share.emit", emit):
            task = asyncio.create_task(serve(self.home, 8766, 1, 2))
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 3)
        self.assertIsNotNone(self.child.returncode)


if __name__ == "__main__":
    unittest.main()
