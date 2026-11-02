import concurrent.futures
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from origo_runtime.workspace import Workspace,OfflineRAG
from origo_runtime.audit import AuditLog
from scripts.verify_audit_checkpoint import verify

class WorkspaceProductTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.project=self.root/"project";self.project.mkdir()
        self.service=Workspace(self.root/"profile")

    def wait_job(self,job):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            state=self.service.jobs[job["id"]]
            if state["state"] not in {"queued","indexing"}: return state
            time.sleep(.02)
        self.fail("Indexing did not finish")

    def test_grants_are_explicit_and_revocable(self):
        with self.assertRaises(PermissionError): self.service.files("unknown")
        (self.project/"notes.md").write_text("An important project note.",encoding="utf-8")
        project=self.service.grant("Project",str(self.project))
        self.assertEqual(self.service.files(project)[0]["name"],"notes.md")
        self.service.revoke(project)
        with self.assertRaises(PermissionError): self.service.engine(project)
        with self.assertRaises(PermissionError): self.service.preview(project,"notes.md")

    def test_no_drive_roots_or_relative_grants(self):
        with self.assertRaises(ValueError): self.service.grant("","relative/path")
        with self.assertRaises(ValueError): self.service.grant("",str(self.root.anchor))

    def test_secret_build_and_traversal_exclusions(self):
        (self.project/".env").write_text("API_KEY=private")
        (self.project/"auth.json").write_text('{}')
        (self.project/"node_modules").mkdir();(self.project/"node_modules/a.js").write_text("private")
        (self.project/"notes.md").write_text("User document text.")
        project=self.service.grant("",str(self.project))
        self.assertEqual([f["name"] for f in self.service.files(project)],["notes.md"])
        for path in ("../outside.txt",".env","node_modules/a.js","auth.json"):
            with self.assertRaises(PermissionError): self.service.preview(project,path)

    def test_offline_hybrid_semantic_retrieval(self):
        from origo_runtime.embeddings import status
        if not status()["installed"]: self.skipTest("Offline embedding asset is not installed")
        with patch("httpx.Client",side_effect=AssertionError("Embedding must not use HTTP")):
            engine=self.service.engine()
            result=engine.ingest_bytes("maintenance.md","text/plain",b"The vehicles require maintenance every six months. Inspect the engine and replace damaged tires.")
            self.assertTrue(result["embedding_indexed"])
            response=self.service.context("How frequently should cars be serviced?")
        self.assertTrue(response["citations"])
        self.assertIn("six months",response["context"])
        self.assertEqual(response["mode"],"hybrid")

    def test_incremental_index_changed_and_deleted_documents(self):
        source=self.project/"README.md";source.write_text("The project release deadline is November third.")
        project=self.service.grant("",str(self.project))
        first=self.wait_job(self.service.index(project));self.assertEqual(first["done"],1)
        with patch.object(OfflineRAG,"ingest_file",side_effect=AssertionError("Unchanged document must be skipped")):
            second=self.wait_job(self.service.index(project));self.assertEqual(second["done"],0)
        source.write_text("The project release deadline changed to November fourth.")
        third=self.wait_job(self.service.index(project));self.assertEqual(third["done"],1)
        source.unlink();self.wait_job(self.service.index(project))
        self.assertEqual(self.service.engine(project).list_documents(),[])

    def test_profile_identity_isolated_unless_both_opt_in(self):
        other=Workspace(self.root/"other-profile")
        self.service.save_identity({"name":"Asha","instructions":"Prefer short answers"})
        self.assertEqual(other.identity()["name"],"")
        self.service.save_identity({"name":"Asha","share_across_profiles":True})
        self.assertEqual(other.identity()["name"],"")
        other.save_identity({"name":"Asha","share_across_profiles":True})
        self.service.save_identity({"name":"Anika","share_across_profiles":True})
        self.assertEqual(other.identity()["name"],"Anika")

    def test_documents_are_project_scoped(self):
        first=self.service.grant("First",str(self.project));other=self.root/"second";other.mkdir()
        second=self.service.grant("Second",str(other))
        self.service.engine(first).ingest_bytes("private.md","text/plain",b"A private project fact about spring flowers.")
        self.assertEqual(self.service.context("spring flowers",second)["citations"],[])

    def test_docx_extraction_is_bounded_plain_text(self):
        path=self.project/"sample.docx"
        with zipfile.ZipFile(path,"w") as archive:
            archive.writestr("word/document.xml",'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>The expedition leaves at dawn.</w:t></w:r></w:p></w:document>')
        project=self.service.grant("",str(self.project))
        self.assertIn("expedition",self.service.preview(project,"sample.docx"))
        result=self.service.engine(project).ingest_file(path,"upload")
        self.assertGreater(result["chunk_count"],0)

    def test_audit_signatures_detect_changes_and_external_anchor_detects_truncation(self):
        log=self.service.audit
        log.append("test",{"model":"local-qwen"});log.append("test",{"model":"vision-reader"})
        checkpoint=log.verify();self.assertTrue(checkpoint["valid"])
        self.assertTrue(verify(log.path,checkpoint)["valid"])
        with log.connect() as db: db.execute("DELETE FROM events WHERE seq=2")
        self.assertTrue(log.verify()["valid"])
        with self.assertRaises(ValueError): verify(log.path,checkpoint)
        with log.connect() as db: db.execute("UPDATE events SET event=? WHERE seq=1",(json.dumps({"seq":1,"previous":"0"*64,"kind":"forged"}),))
        self.assertFalse(log.verify()["valid"])

    def test_audit_append_is_ordered_under_concurrency(self):
        log=self.service.audit
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i:log.append("test",{"index":i}),range(24)))
        result=log.verify();self.assertTrue(result["valid"]);self.assertEqual(result["count"],24)

    def test_optimized_python_still_rejects_valid_signatures_at_wrong_sequences(self):
        log=self.service.audit
        log.append("fixture",{});log.append("fixture",{})
        # Retain every signed event unchanged, but break the database sequence.
        with log.connect() as db:db.execute("UPDATE events SET seq=seq+10")
        self.assertFalse(log.verify()["valid"])
        code="import sys,json;sys.path.insert(0,sys.argv[1]);from origo_runtime.audit import AuditLog;print(json.dumps(AuditLog(sys.argv[2]).verify()))"
        result=subprocess.run([sys.executable,"-O","-c",code,str(Path(__file__).resolve().parents[1]),str(self.service.home)],
                              capture_output=True,text=True,timeout=25,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        self.assertEqual(result.returncode,0,result.stderr[-300:])
        report=json.loads(result.stdout)
        self.assertFalse(report["valid"])
        self.assertEqual(report["first_invalid"],11)

    def test_checkpoint_verifier_does_not_create_missing_database(self):
        checkpoint=self.service.audit.verify();missing=self.root/"missing.sqlite3"
        with self.assertRaises(sqlite3.OperationalError):verify(missing,checkpoint)
        self.assertFalse(missing.exists())

    def test_malformed_document_does_not_enter_library(self):
        path=self.project/"broken.docx";path.write_bytes(b"Not a zip file")
        with self.assertRaises(ValueError): self.service.engine().ingest_file(path,"upload")
        self.assertEqual(self.service.engine().list_documents(),[])

if __name__=="__main__": unittest.main()
