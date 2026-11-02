from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.sqlite_safety import DatabaseSafetyError, configure_database, journal_mode, open_database

ROOT = Path(__file__).resolve().parents[1]


class DatabaseSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def mode(self, path):
        with closing(sqlite3.connect(path)) as db:
            return db.execute("PRAGMA journal_mode").fetchone()[0]

    def test_version_boundaries_and_documented_backports(self):
        cases = {(3,6,23):"delete",(3,7,0):"delete",(3,44,5):"delete",(3,44,6):"wal",
                 (3,44,10):"wal",(3,45,0):"delete",(3,50,4):"delete",(3,50,6):"delete",
                 (3,50,7):"wal",(3,51,0):"delete",(3,51,2):"delete",(3,51,3):"wal",(3,52,0):"wal"}
        for version, expected in cases.items():
            with self.subTest(version=version):
                self.assertEqual(journal_mode(version),expected)
                self.assertEqual(journal_mode(version,prefer_wal=False),"delete")
        for unknown in [(),"3.51.3",(3,True,4),(-1,0,0)]:
            self.assertEqual(journal_mode(unknown),"delete")

    def test_runtime_mode_and_full_sync_on_every_connection(self):
        path = self.root/"state.sqlite3"
        for _ in range(3):
            with closing(open_database(path,timeout=1)) as db:
                self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0],journal_mode())
                self.assertEqual(db.execute("PRAGMA synchronous").fetchone()[0],2)
        with closing(open_database(":memory:")) as db:
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0],"memory")

    def test_existing_wal_data_migrates_via_sqlite(self):
        path = self.root/"legacy.sqlite3"
        with closing(sqlite3.connect(path)) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE fixture(id INTEGER PRIMARY KEY,value BLOB)")
            db.execute("INSERT INTO fixture VALUES(1,?)",(b"retained"*10000,)); db.commit()
        self.assertEqual(self.mode(path),"wal")
        # Exercise migration on any test runner version; the version selector
        # itself is separately tested above against the vendor's boundaries.
        with patch("app.sqlite_safety.journal_mode",return_value="delete"):
            with closing(open_database(path)) as db:
                self.assertEqual(db.execute("SELECT value FROM fixture").fetchone()[0],b"retained"*10000)
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
        self.assertEqual(self.mode(path),"delete")

    def test_busy_legacy_database_refuses_then_recovers_without_data_loss(self):
        path = self.root/"busy.sqlite3"
        with closing(sqlite3.connect(path)) as owner:
            owner.execute("PRAGMA journal_mode=WAL"); owner.execute("CREATE TABLE fixture(value TEXT)")
            owner.execute("INSERT INTO fixture VALUES('retained')"); owner.commit()
            owner.execute("BEGIN"); owner.execute("SELECT * FROM fixture").fetchone()
            with patch("app.sqlite_safety.journal_mode",return_value="delete"):
                with self.assertRaises(DatabaseSafetyError) as error: open_database(path,timeout=.03)
            self.assertNotIn(str(path),str(error.exception))
            self.assertEqual(owner.execute("SELECT value FROM fixture").fetchone()[0],"retained")
        with patch("app.sqlite_safety.journal_mode",return_value="delete"):
            with closing(open_database(path)) as db:
                self.assertEqual(db.execute("SELECT value FROM fixture").fetchone()[0],"retained")

    def test_corruption_refuses_without_replacing_the_file(self):
        path = self.root/"invalid.sqlite3"; path.write_bytes(b"fixture invalid bytes")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(DatabaseSafetyError): open_database(path)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)

    def test_failed_configuration_closes_its_connection(self):
        path = self.root/"failed.sqlite3"
        with patch("app.sqlite_safety.configure_database",side_effect=DatabaseSafetyError("fixture")):
            with self.assertRaises(DatabaseSafetyError): open_database(path)
        path.unlink()  # Windows refuses this if the failed opener leaks its handle.
        self.assertFalse(path.exists())

    def test_all_product_stores_preserve_data_keys_and_signed_chain_on_migration(self):
        from app.store import Store
        from app.rag import RAGEngine
        from origo_runtime.workspace import Workspace
        from origo_runtime.conversation_records import ConversationRecords
        with patch.dict(os.environ,{"INDRA_DATA_DIR":str(self.root/"store"),"RAG_EMBEDDING_MODEL":""}):
            store = Store(); store.set_setting("fixture","retained")
            rag = RAGEngine(self.root/"knowledge")
            rag.ingest_bytes("fixture.txt","text/plain",b"The service interval is six months.")
            home = self.root/"profile"; workspace = Workspace(home,shared_root=self.root/"shared")
            folder = self.root/"project"; folder.mkdir(); project = workspace.grant("Fixture",str(folder))
            guard = workspace.content_guard(); guard.mark("chat","turn","fixture")
            marker = workspace.canaries().create("fixture")
            records = ConversationRecords(workspace.root)
            records.save("chat",[{"id":"entry","role":"user","text":"retained"}])
            key_path = workspace.audit.root/"signing-key.pem"; key_hash = hashlib.sha256(key_path.read_bytes()).hexdigest()
            head = workspace.audit.recent()[0]["hash"]
            paths = [store.db_path,rag.db_path,workspace.db_path,guard.path,workspace.canaries().path,workspace.audit.path,records.path]
            for path in paths:
                with closing(sqlite3.connect(path)) as db: db.execute("PRAGMA journal_mode=WAL")
            with patch("app.sqlite_safety.journal_mode",return_value="delete"):
                self.assertEqual(Store().get_setting("fixture"),"retained")
                self.assertEqual(RAGEngine(self.root/"knowledge").status()["documents"],1)
                self.assertEqual(Workspace(home,shared_root=self.root/"shared").project(project)["name"],"Fixture")
                self.assertTrue(guard.exposed("chat","turn"))
                self.assertEqual(workspace.canaries().matches(marker["token"]),[marker["id"]])
                self.assertEqual(records.list("chat")[0]["text"],"retained")
                self.assertTrue(workspace.audit.verify()["valid"])
            self.assertEqual(hashlib.sha256(key_path.read_bytes()).hexdigest(),key_hash)
            self.assertEqual(workspace.audit.recent()[0]["hash"],head)
            self.assertTrue(all(self.mode(path)=="delete" for path in paths))

    def test_concurrent_audit_writers_in_separate_processes_preserve_every_signature(self):
        from origo_runtime.audit import AuditLog
        audit = AuditLog(self.root/"profile")
        code = """import sys
sys.path.insert(0,sys.argv[1])
from origo_runtime.audit import AuditLog
audit=AuditLog(sys.argv[2])
for i in range(12): audit.append('fixture.concurrent',{'worker':sys.argv[3],'index':i})
"""
        def worker(index):
            return subprocess.run([sys.executable,"-c",code,str(ROOT),str(self.root/"profile"),str(index)],
                                  capture_output=True,text=True,timeout=40,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(worker,range(4)))
        self.assertTrue(all(row.returncode==0 for row in results),[(r.returncode,r.stderr[-300:]) for r in results])
        self.assertEqual(len(audit.recent()),48)
        self.assertTrue(audit.verify()["valid"])
        self.assertEqual(self.mode(audit.path),journal_mode())

    def test_crashed_writer_rolls_back_and_retains_committed_data(self):
        path = self.root/"crash.sqlite3"
        with closing(open_database(path,prefer_wal=False)) as db:
            db.execute("CREATE TABLE fixture(value BLOB)")
            db.execute("INSERT INTO fixture VALUES(?)",(b"committed",)); db.commit()
        code = """import sys,os
sys.path.insert(0,sys.argv[1])
from app.sqlite_safety import open_database
db=open_database(sys.argv[2],prefer_wal=False)
db.execute('PRAGMA cache_size=1')
db.execute('BEGIN IMMEDIATE')
db.execute('UPDATE fixture SET value=?',(b'uncommitted'*200000,))
os._exit(0)
"""
        result = subprocess.run([sys.executable,"-c",code,str(ROOT),str(path)],timeout=30,
            capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        self.assertEqual(result.returncode,0)
        with closing(open_database(path,prefer_wal=False)) as db:
            self.assertEqual(db.execute("SELECT value FROM fixture").fetchone()[0],b"committed")
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
