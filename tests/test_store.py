import os, tempfile, unittest
from pathlib import Path
from app.store import Store

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = os.environ.get('INDRA_DATA_DIR')
        os.environ['INDRA_DATA_DIR'] = self.temp.name
        self.store = Store()
    def tearDown(self):
        if self.old is None: os.environ.pop('INDRA_DATA_DIR', None)
        else: os.environ['INDRA_DATA_DIR'] = self.old
        self.temp.cleanup()
    def test_claim_is_single_winner(self):
        action = self.store.add_action({'kind':'write_file','path':'a.txt','content':'hi'})
        self.assertIsNotNone(self.store.claim_action(action['id']))
        self.assertIsNone(self.store.claim_action(action['id']))
    def test_run_snapshots_survive_reload(self):
        self.store.save_run({'run_id':'r1','status':'completed'})
        self.assertEqual(self.store.list_runs()[0]['run_id'], 'r1')
    def test_action_status_update(self):
        action = self.store.add_action({'kind':'write_file','path':'a.txt','content':'hi'})
        self.store.update_action(action['id'],'rejected')
        self.assertEqual(self.store.list_actions()[0]['status'],'rejected')

if __name__ == '__main__': unittest.main()
