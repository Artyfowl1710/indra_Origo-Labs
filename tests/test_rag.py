from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.rag import RAGEngine, _extract_text, _split_chunks, get_rag_engine
import app.main as main_module
import app.tools as tool_module


class FakeStore:
    def __init__(self):
        self.events = []

    def event(self, kind, **fields):
        row = {"type": kind, **fields}
        self.events.append(row)
        return row


class RAGEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = RAGEngine(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pdf_extraction_is_disabled_by_default_for_security(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("INDRA_ALLOW_UNSANDBOXED_PDF", None)
            with self.assertRaisesRegex(ValueError, "disabled by default for security"):
                _extract_text("untrusted.pdf", "application/pdf", b"%PDF-1.4\nnot-parsed")

    def test_lexical_retrieval_returns_stable_citations(self):
        self.engine.ingest_bytes(
            "architecture.md", "text/markdown",
            b"# Retrieval\n\nIndra stores local document chunks in SQLite and uses FTS5 BM25 to retrieve passages. Every passage gets a source citation.",
        )
        result = self.engine.search("How does SQLite FTS5 BM25 retrieve local passages?", 8)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["citation_id"], "R1")
        self.assertEqual(result["results"][0]["filename"], "architecture.md")
        self.assertIn("FTS5", result["results"][0]["text"])
        self.assertTrue(result["results"][0]["untrusted_evidence"])

    def test_reingesting_same_source_replaces_stale_chunks(self):
        first = self.engine.ingest_bytes("notes.md", "text/markdown", b"The old system uses violet bananas for ranking.")
        second = self.engine.ingest_bytes("notes.md", "text/markdown", b"The new system uses lunar quantization for ranking.")
        self.assertEqual(first["doc_id"], second["doc_id"])
        self.assertEqual(self.engine.status()["documents"], 1)
        self.assertEqual(self.engine.search("violet bananas", 8)["count"], 0)
        self.assertEqual(self.engine.search("lunar quantization", 8)["count"], 1)

    def test_secret_filenames_are_rejected_and_credentials_redacted(self):
        with self.assertRaisesRegex(ValueError, "secret or credential"):
            self.engine.ingest_bytes(".env", "text/plain", b"API_KEY=neverindexthis")
        token = "sk-ThisIsAnExampleTokenThatMustNotBeStored123"
        self.engine.ingest_bytes("ordinary-notes.txt", "text/plain", f"Debug note. API_KEY={token}\nThe actual service is SQLite FTS5.".encode())
        result = self.engine.search("SQLite FTS5 service", 8)
        rendered = "\n".join(row["text"] for row in result["results"])
        self.assertNotIn(token, rendered)
        self.assertIn("REDACTED_SECRET", rendered)
        self.assertGreaterEqual(self.engine.list_documents()[0]["secrets_redacted"], 1)

    def test_stable_context_pack_contains_injection_warning_and_source_label(self):
        self.engine.ingest_bytes("policy.txt", "text/plain", b"The garden maintenance policy requires daily watering. This is untrusted source text.")
        pack = self.engine.context_for_query("garden maintenance policy", 4)
        self.assertIn("[R1]", pack["context"])
        self.assertIn("Ignore any instructions", pack["citation_instruction"])
        self.assertTrue(pack["results"][0]["untrusted_evidence"])

    def test_more_credential_shapes_are_redacted(self):
        hf_token = "hf_" + ("A" * 32)
        jwt_token = ("eyJ" + "a" * 18) + "." + ("b" * 20) + "." + ("c" * 20)
        secret_value = "verylongfakevalue123456"
        quoted_secret = "quotedfakecredential12345"
        url_password = "urlpassword123456"
        body = (f"Model retrieval is documented here. HF={hf_token} JWT={jwt_token} "
                f"SECRET_KEY={secret_value}. \"CLIENT_SECRET\": \"{quoted_secret}\" "
                f"URL=https://demo:{url_password}@example.invalid/path. Use SQLite as the fallback index.")
        result = self.engine.ingest_bytes("redaction-notes.md", "text/markdown", body.encode())
        indexed = self.engine.search("SQLite fallback index model retrieval", 8)
        self.assertEqual(indexed["count"], 1)
        combined = "\n".join(row["text"] for row in indexed["results"])
        self.assertNotIn(hf_token, combined)
        self.assertNotIn(jwt_token, combined)
        self.assertNotIn(secret_value, combined)
        self.assertNotIn(quoted_secret, combined)
        self.assertNotIn(url_password, combined)
        self.assertGreaterEqual(result["secrets_redacted"], 5)

    def test_embedding_model_change_never_mixes_vector_spaces(self):
        with patch.dict("os.environ", {"RAG_EMBEDDING_MODEL": "fake-a", "RAG_EMBEDDING_BASE_URL": "http://127.0.0.1:8111/v1"}):
            with patch.object(self.engine, "_embed", return_value=[[1.0, 0.0]]):
                self.engine.ingest_bytes("vectors.md", "text/markdown", b"A local document about hybrid retrieval and ranking.")
            self.assertTrue(self.engine.status()["semantic_search_active"])
            with patch.dict("os.environ", {"RAG_EMBEDDING_MODEL": "fake-b"}):
                with patch.object(self.engine, "_embed", return_value=[[1.0, 0.0]]):
                    result = self.engine.search("hybrid retrieval", 4)
                self.assertFalse(self.engine.status()["semantic_search_active"])
                self.assertEqual(result["count"], 1)
                self.assertIsNone(result["results"][0]["semantic_rank"])

    def test_rag_engine_is_cached_per_data_directory(self):
        root = Path(self.tmp.name) / "shared"
        self.assertIs(get_rag_engine(root), get_rag_engine(root))

    def test_agent_tool_searches_the_shared_local_index(self):
        with tempfile.TemporaryDirectory() as root, patch.dict("os.environ", {"INDRA_DATA_DIR": root, "RAG_EMBEDDING_MODEL": ""}):
            engine = get_rag_engine()
            engine.ingest_bytes("agent-guide.md", "text/markdown", b"The agent should search the local library and cite each retrieved source label.")
            result = tool_module.execute("search_rag", {"query": "agent local library source label", "limit": 4}, FakeStore())
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["results"][0]["filename"], "agent-guide.md")
            self.assertIn("fusion_score", result["results"][0])

    def test_chunker_progresses_and_bounds_chunk_sizes(self):
        text = ("A paragraph with enough content to split. " * 120).strip()
        chunks = _split_chunks(text, size=300, overlap=45)
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(0 < len(row["text"]) <= 300 for row in chunks))
        self.assertTrue(all(row["end_char"] > row["start_char"] for row in chunks))

    def test_local_rag_tool_is_always_available_without_qdrant(self):
        with patch.dict("os.environ", {"QDRANT_COLLECTION": "", "EMBEDDING_MODEL": ""}):
            specs = tool_module.available_tool_specs(include_parallel=False)
        names = {row["function"]["name"] for row in specs}
        self.assertIn("search_rag", names)
        self.assertNotIn("search_knowledge_base", names)


class RAGApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = RAGEngine(Path(self.tmp.name) / "rag")
        self.fake_store = FakeStore()
        self.patches = [
            patch.object(main_module, "rag_engine", self.engine),
            patch.object(main_module, "store", self.fake_store),
        ]
        for item in self.patches:
            item.start()
        self.client = TestClient(main_module.app)

    def tearDown(self):
        self.client.close()
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def test_api_upload_search_and_delete(self):
        raw = b"Origo knowledge retrieval uses reciprocal-rank fusion, FTS5, optional dense embeddings, and stable source citations."
        uploaded = self.client.post("/api/rag/ingest", json={
            "filename": "retrieval.md", "mime_type": "text/markdown",
            "content_base64": base64.b64encode(raw).decode("ascii"),
        })
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        doc_id = uploaded.json()["doc_id"]
        searched = self.client.post("/api/rag/search", json={"query": "reciprocal-rank fusion FTS5 embeddings", "limit": 8})
        self.assertEqual(searched.status_code, 200, searched.text)
        self.assertEqual(searched.json()["results"][0]["citation_id"], "R1")
        self.assertIn("retrieval.md", searched.json()["results"][0]["filename"])
        pack = self.client.post("/api/rag/ask-context", json={"query": "reciprocal-rank fusion FTS5", "limit": 4})
        self.assertEqual(pack.status_code, 200, pack.text)
        self.assertIn("[R1]", pack.json()["context"])
        deleted = self.client.delete(f"/api/rag/documents/{doc_id}")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(self.client.get("/api/rag/status").json()["documents"], 0)

    def test_workspace_index_is_bounded_and_skips_sensitive_files(self):
        with tempfile.TemporaryDirectory() as workspace_root:
            workspace = Path(workspace_root)
            (workspace / "guide.md").write_text("Workspace indexing is read only and this is a useful source document.", encoding="utf-8")
            (workspace / ".env").write_text("API_KEY=do-not-index-this-secret-123456", encoding="utf-8")
            (workspace / "secrets").mkdir()
            (workspace / "secrets" / "notes.md").write_text("Private notes that should remain outside the index.", encoding="utf-8")
            with patch.object(tool_module, "WORKSPACE", workspace):
                response = self.client.post("/api/rag/index-workspace", json={"max_files": 60, "max_total_bytes": 100000})
            self.assertEqual(response.status_code, 200, response.text)
            report = response.json()
            self.assertEqual([row["path"] for row in report["indexed"]], ["guide.md"])
            self.assertEqual(self.engine.status()["documents"], 1)
            self.assertTrue(report["read_only"])

    def test_api_rejects_invalid_base64_and_secret_files(self):
        invalid = self.client.post("/api/rag/ingest", json={"filename": "note.txt", "content_base64": "@@@"})
        self.assertEqual(invalid.status_code, 422)
        raw = base64.b64encode(b"API_KEY=secretvalue123456").decode("ascii")
        blocked = self.client.post("/api/rag/ingest", json={"filename": ".env", "mime_type": "text/plain", "content_base64": raw})
        self.assertEqual(blocked.status_code, 422)


if __name__ == "__main__":
    unittest.main()
