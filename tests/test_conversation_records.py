import tempfile,unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from origo_runtime.conversation_records import ConversationRecords

class ConversationRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.addCleanup(self.temp.cleanup);self.book=ConversationRecords(Path(self.temp.name))
    def entry(self,key="turn-1",text="Hello"):
        return {"id":key,"role":"user","kind":"voice","text":text,"model":"fixture-model","provider":"fixture"}
    def test_fragment_updates_are_idempotent_and_visible_after_cursor(self):
        self.book.save("chat-1",[self.entry()]);initial=self.book.list("chat-1")[0]
        self.book.save("chat-1",[self.entry(text="Hello world")]);rows=self.book.list("chat-1",initial["seq"])
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]["text"],"Hello world");self.assertEqual(rows[0]["created"],initial["created"])
        self.assertEqual(len(self.book.list("chat-1")),1)
    def test_cross_chat_overwrite_and_invalid_identifiers_are_rejected(self):
        self.book.save("chat-1",[self.entry()])
        with self.assertRaises(ValueError):self.book.save("chat-2",[self.entry()])
        with self.assertRaises(ValueError):self.book.list("../private")
        self.assertEqual(self.book.list("chat-2"),[])
    def test_runtime_actions_cannot_be_forged_by_the_client_save_path(self):
        row={**self.entry(),"kind":"action","role":"note"}
        with self.assertRaises(ValueError):self.book.save("chat-1",[row])
        self.book.save("chat-1",[row],source="runtime")
        self.assertEqual(self.book.list("chat-1")[0]["source"],"runtime")
        with self.assertRaises(ValueError):self.book.save("chat-1",[self.entry(text="overwritten")])
        self.assertEqual(self.book.list("chat-1")[0]["kind"],"action")
    def test_writes_survive_reopening_and_remain_profile_local(self):
        self.book.save("chat-1",[self.entry()]);reopened=ConversationRecords(Path(self.temp.name))
        self.assertEqual(reopened.list("chat-1")[0]["text"],"Hello")
        self.assertEqual(ConversationRecords(Path(self.temp.name)/"other-profile").list("chat-1"),[])
    def test_batch_failure_rolls_back_and_concurrent_writes_are_preserved(self):
        with self.assertRaises(ValueError):self.book.save("chat-1",[self.entry(),self.entry("invalid/path")])
        self.assertEqual(self.book.list("chat-1"),[])
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda n:self.book.save("chat-1",[self.entry(f"turn-{n}")]),range(20)))
        self.assertEqual(len(self.book.list("chat-1")),20)
