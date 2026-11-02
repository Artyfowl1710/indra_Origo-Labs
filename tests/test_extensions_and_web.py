from __future__ import annotations
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import extensions, web_tools
from app.main import app
from app.tools import available_tool_specs


class WebPolicyTests(unittest.TestCase):
    def test_blocks_private_ip_ranges_local_hosts_custom_ports_and_url_credentials(self):
        blocked = [
            "https://127.0.0.1/", "https://10.0.0.10/", "https://192.168.1.4/",
            "https://169.254.169.254/latest/meta-data/", "https://[::1]/", "https://localhost/",
            "https://router.local/", "https://example.com:8443/", "https://user:pass@example.com/",
        ]
        for value in blocked:
            with self.subTest(value=value), self.assertRaises(web_tools.WebPolicyError):
                web_tools.validate_public_url(value, resolve_dns=False)

    def test_http_requires_explicit_opt_in(self):
        with patch.dict(os.environ, {"INDRA_WEB_ALLOW_HTTP": "false"}):
            with self.assertRaises(web_tools.WebPolicyError):
                web_tools.validate_public_url("http://example.com/", resolve_dns=False)
        with patch.dict(os.environ, {"INDRA_WEB_ALLOW_HTTP": "true"}):
            self.assertEqual(web_tools.validate_public_url("http://example.com/a#frag", resolve_dns=False), "http://example.com/a")

    def test_parser_extracts_page_text_and_links_but_skips_scripts_and_navigation(self):
        parser = web_tools._PageParser("https://example.org/a")
        parser.feed('<html><head><title>Study Guide</title><meta name="description" content="A useful guide"></head><body><nav>Menu noise</nav><h1>Important fact</h1><script>steal secrets</script><a href="/paper">Read paper</a></body></html>')
        result = parser.output()
        self.assertIn("Study Guide", result["title"])
        self.assertEqual(result["description"], "A useful guide")
        self.assertIn("Important fact", result["text"])
        self.assertNotIn("Menu noise", result["text"])
        self.assertNotIn("steal secrets", result["text"])
        self.assertEqual(result["links"][0]["url"], "https://example.org/paper")

    def test_fetch_page_rejects_private_targets_before_network_access(self):
        result = web_tools.fetch_page("http://127.0.0.1:8080/admin")
        self.assertTrue(result.get("policy_block"))
        self.assertIn("HTTPS", result["error"])


    def test_public_ipv6_literal_is_normalized_with_brackets(self):
        self.assertEqual(web_tools.validate_public_url("https://[2606:4700:4700::1111]/path", resolve_dns=False),
                         "https://[2606:4700:4700::1111]/path")

    def test_dns_resolution_to_private_address_is_rejected(self):
        with patch("app.web_tools.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.8", 443))]):
            with self.assertRaises(web_tools.WebPolicyError):
                web_tools.validate_public_url("https://public-looking.example.org/path")

    def test_robots_denial_precedes_page_fetch(self):
        web_tools._robots_cache.clear()
        with patch.object(web_tools, "validate_public_url", return_value="https://example.org/private"), \
             patch.object(web_tools, "_robots_allowed", return_value=(False, "disallowed by robots.txt")), \
             patch.object(web_tools, "_fetch_bytes") as fetch:
            result = web_tools.fetch_page("https://example.org/private")
        self.assertTrue(result.get("policy_block"))
        self.assertIn("robots.txt", result["error"])
        fetch.assert_not_called()


    def test_robots_policy_cache_evaluates_each_path_not_first_url_result(self):
        class Response:
            status_code = 200
            def iter_bytes(self):
                yield b"User-agent: *\nDisallow: /private\nAllow: /\n"
        class ResponseContext:
            def __enter__(self): return Response()
            def __exit__(self, *args): return False
        class Client:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def stream(self, *args, **kwargs): return ResponseContext()
        web_tools._robots_cache.clear()
        with patch.object(web_tools, "validate_public_url", side_effect=lambda url, resolve_dns=True: url), \
             patch.object(web_tools, "_rate_limit"), patch("app.web_tools.httpx.Client", Client):
            self.assertTrue(web_tools._robots_allowed("https://example.org/public")[0])
            allowed, reason = web_tools._robots_allowed("https://example.org/private/secret")
        self.assertFalse(allowed)
        self.assertIn("disallowed", reason)

    def test_domain_allowlist_is_enforced_and_malformed_config_fails_closed(self):
        with patch.dict(os.environ, {"INDRA_WEB_ALLOWED_DOMAINS": "example.org, *.research.net"}):
            self.assertEqual(web_tools.validate_public_url("https://sub.example.org", resolve_dns=False), "https://sub.example.org/")
            self.assertEqual(web_tools.validate_public_url("https://papers.research.net", resolve_dns=False), "https://papers.research.net/")
            with self.assertRaises(web_tools.WebPolicyError):
                web_tools.validate_public_url("https://notexample.org", resolve_dns=False)
        with patch.dict(os.environ, {"INDRA_WEB_ALLOWED_DOMAINS": ",,,"}):
            with self.assertRaises(web_tools.WebPolicyError):
                web_tools.validate_public_url("https://example.org", resolve_dns=False)

    def test_redirect_target_is_revalidated_before_second_request(self):
        class Response:
            status_code = 302
            headers = {"location": "http://127.0.0.1/admin"}
        class ResponseContext:
            def __enter__(self): return Response()
            def __exit__(self, *args): return False
        class Client:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def stream(self, *args, **kwargs): return ResponseContext()
        with patch("app.web_tools.httpx.Client", Client), patch.object(web_tools, "_rate_limit"), \
             patch.object(web_tools, "validate_public_url", side_effect=["https://public.example/", web_tools.WebPolicyError("private redirect blocked")]) as validate:
            with self.assertRaises(web_tools.WebPolicyError):
                web_tools._fetch_bytes("https://public.example/")
        self.assertEqual(validate.call_count, 2)

    def test_allowlisted_research_can_use_fixed_search_provider_but_filters_sources(self):
        html = b"<html><body><a class='result__a' href='https://example.org/paper'>Allowed paper</a><a class='result__a' href='https://evil.test/steal'>Other source</a></body></html>"
        class Response:
            status_code = 200
            headers = {"content-type": "text/html; charset=utf-8"}
            def iter_bytes(self): yield html
        class ResponseContext:
            def __enter__(self): return Response()
            def __exit__(self, *args): return False
        class Client:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def stream(self, *args, **kwargs): return ResponseContext()
        with patch.dict(os.environ, {"INDRA_WEB_ALLOWED_DOMAINS": "example.org"}), \
             patch("app.web_tools.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("8.8.8.8", 443))]), \
             patch("app.web_tools.httpx.Client", Client), patch.object(web_tools, "_rate_limit"):
            result = web_tools.search_web("test query", limit=5)
        self.assertEqual([row["url"] for row in result["results"]], ["https://example.org/paper"])

    def test_same_host_crawl_is_bounded_and_does_not_follow_external_links(self):
        pages = {
            "https://example.org/": {"url": "https://example.org/", "title": "Home", "description": "", "text": "a" * 1000,
                                     "links": [{"url": "https://example.org/a", "title": "A"}, {"url": "https://evil.example/a", "title": "External"}]},
            "https://example.org/a": {"url": "https://example.org/a", "title": "A", "description": "", "text": "b" * 1000,
                                      "links": [{"url": "https://example.org/b", "title": "B"}]},
        }
        with patch.object(web_tools, "validate_public_url", side_effect=lambda url, resolve_dns=True: url.split("#", 1)[0]), \
             patch.object(web_tools, "fetch_page", side_effect=lambda url, max_chars, deadline=None: {**pages[url], "text": pages[url]["text"][:max_chars]}):
            result = web_tools.scrape_site("https://example.org/", max_pages=2, max_chars=2000)
        self.assertEqual(result["pages_fetched"], 2)
        self.assertLessEqual(result["characters"], 2000)
        self.assertEqual([row["url"] for row in result["pages"]], ["https://example.org/", "https://example.org/a"])

    def test_search_and_fetch_research_workflow_bounds_source_text(self):
        with patch.object(web_tools, "search_web", return_value={"provider": "test", "results": [
                {"url": f"https://example.org/{n}", "title": f"Page {n}"} for n in range(3)]}), \
             patch.object(web_tools, "fetch_page", side_effect=lambda url, chars, deadline=None: {"url": url, "title": url,
                "text": "x" * 5000, "description": "desc", "cache": "miss", "robots": "allowed"}):
            result = web_tools.research_web("test query", max_pages=3, max_chars=2000)
        self.assertEqual(result["pages_fetched"], 3)
        self.assertLessEqual(result["characters"], 2000)
        self.assertEqual(result["sources"][0]["url"], "https://example.org/0")

    def test_web_tools_are_registered_and_http_route_returns_policy_errors(self):
        names = {row["function"]["name"] for row in available_tool_specs()}
        self.assertIn("web_search", names)
        self.assertIn("web_fetch", names)
        self.assertIn("web_research", names)
        self.assertIn("web_crawl", names)
        with TestClient(app) as client:
            response = client.post("/api/web/fetch", json={"url": "http://127.0.0.1/admin"})
            self.assertEqual(response.status_code, 400, response.text)
            self.assertIn("HTTPS", response.json()["detail"])


class SkillRegistryTests(unittest.TestCase):
    def test_builtin_skills_have_ids_and_content_can_be_loaded(self):
        rows = extensions.list_skills()
        ids = {row["id"] for row in rows}
        self.assertTrue({"web-research", "code-review", "study-coach", "research-planner"}.issubset(ids))
        skill = extensions.load_skill("web-research")
        self.assertIn("primary sources", skill["content"])
        self.assertNotIn("path", skill)

    def test_plugins_are_disabled_by_default_and_require_two_gates(self):
        plugin_root = Path(__file__).parent / ".." / "plugins"
        with patch.object(extensions, "PLUGINS_ROOT", plugin_root.resolve()), patch.dict(os.environ, {"INDRA_ENABLE_LOCAL_HTTP_PLUGINS": "false"}):
            rows = extensions.list_plugins()
            self.assertTrue(rows)
            self.assertFalse(any(row["enabled"] for row in rows))
            self.assertEqual(extensions.get_plugin_tool_specs(), [])
        with patch.object(extensions, "PLUGINS_ROOT", plugin_root.resolve()), patch.dict(os.environ, {"INDRA_ENABLE_LOCAL_HTTP_PLUGINS": "true"}):
            rows = extensions.list_plugins()
            # Example remains disabled even when the global gate is open.
            self.assertFalse(any(row["enabled"] for row in rows))


    def _write_plugin(self, root: Path, *, read_only=True):
        folder = root / "research-notes"
        folder.mkdir(parents=True, exist_ok=True)
        manifest = {"id": "research-notes", "name": "Research Notes", "version": "1.0.0", "description": "test",
                    "enabled": True, "base_url": "http://127.0.0.1:9911", "tools": [{
                        "name": "search_notes", "method": "POST", "read_only": read_only, "endpoint": "/search",
                        "input_schema": {"type": "object", "properties": {"query": {"type": "string", "maxLength": 100}},
                                         "required": ["query"], "additionalProperties": False}}]}
        (folder / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def test_enabled_read_only_plugin_is_exposed_but_mutating_plugin_is_not(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_plugin(root, read_only=True)
            with patch.object(extensions, "PLUGINS_ROOT", root), patch.dict(os.environ, {"INDRA_ENABLE_LOCAL_HTTP_PLUGINS": "true"}):
                names = [row["function"]["name"] for row in extensions.get_plugin_tool_specs()]
                self.assertEqual(names, ["plugin__research-notes__search_notes"])
            self._write_plugin(root, read_only=False)
            with patch.object(extensions, "PLUGINS_ROOT", root), patch.dict(os.environ, {"INDRA_ENABLE_LOCAL_HTTP_PLUGINS": "true"}):
                self.assertEqual(extensions.get_plugin_tool_specs(), [])

    def test_plugin_streaming_response_is_bounded_and_validated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_plugin(root)
            with patch.object(extensions, "PLUGINS_ROOT", root), patch.dict(os.environ, {"INDRA_ENABLE_LOCAL_HTTP_PLUGINS": "true"}):
                http_client = MagicMock()
                response_context = MagicMock()
                response = response_context.__enter__.return_value
                response.status_code = 200
                response.headers = {"content-type": "application/json"}
                response.iter_bytes.return_value = [b'{"notes":["safe"]}']
                http_client.__enter__.return_value.stream.return_value = response_context
                with patch("app.extensions.httpx.Client", return_value=http_client):
                    result = extensions.execute_plugin_tool("plugin__research-notes__search_notes", {"query": "paper"})
                self.assertEqual(result["data"], {"notes": ["safe"]})
                response.iter_bytes.return_value = [b"x" * (extensions.MAX_PLUGIN_RESPONSE_BYTES + 1)]
                with patch("app.extensions.httpx.Client", return_value=http_client):
                    oversized = extensions.execute_plugin_tool("plugin__research-notes__search_notes", {"query": "paper"})
                self.assertIn("16 KB", oversized["error"])

    def test_plugin_numeric_constraints_and_schema_size_are_bounded(self):
        self.assertFalse(extensions._valid_schema({"type": "object", "properties": {"n": {"type": "integer", "enum": list(range(60))}},
                                                   "required": [], "additionalProperties": False}))
        schema = {"type": "object", "properties": {"n": {"type": "integer", "minimum": 1, "maximum": 4}},
                  "required": ["n"], "additionalProperties": False}
        self.assertTrue(extensions._valid_schema(schema))

    def test_remote_plugin_endpoint_is_rejected(self):
        with self.assertRaises(ValueError):
            extensions._loopback_base_url("https://example.com/plugin")
        with self.assertRaises(ValueError):
            extensions._loopback_base_url("http://127.0.0.1:9999/../../admin")

    def test_invalid_plugin_schema_is_rejected(self):
        self.assertFalse(extensions._valid_schema({"type": "object", "properties": {"x": {"type": "string"}}}))
        self.assertTrue(extensions._valid_schema({"type": "object", "properties": {"x": {"type": "string", "maxLength": 100}}, "required": ["x"], "additionalProperties": False}))

    def test_extensions_api_reports_skills_plugins_and_sandbox_without_leaking_manifest_paths(self):
        with TestClient(app) as client:
            response = client.get("/api/extensions")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data["skills"])
        self.assertIn("plugins", data)
        self.assertIn("sandbox", data)
        self.assertNotIn("manifest_path", json.dumps(data))
