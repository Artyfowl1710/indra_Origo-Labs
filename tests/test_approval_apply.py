import hashlib, os, tempfile, unittest
from pathlib import Path
from fastapi.testclient import TestClient
import app.main as main_module
from app.store import Store

class ApprovalApplyTests(unittest.TestCase):
    def test_approved_overwrite_creates_backup_and_applies_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'workspace'; root.mkdir()
            target = root / 'hello.txt'; target.write_text('old value', encoding='utf-8')
            backup_dir = Path(tmp) / 'backups'
            old_store, old_safe = main_module.store, main_module.safe_path
            old_workspace, old_backup, old_data = os.environ.get('INDRA_WORKSPACE'), os.environ.get('INDRA_BACKUP_DIR'), os.environ.get('INDRA_DATA_DIR')
            os.environ['INDRA_WORKSPACE'] = str(root)
            os.environ['INDRA_BACKUP_DIR'] = str(backup_dir)
            os.environ['INDRA_DATA_DIR'] = str(Path(tmp) / 'data')
            main_module.store = Store()
            main_module.safe_path = lambda rel: (root / rel).resolve()
            try:
                action = main_module.store.add_action({'kind':'write_file','path':'hello.txt','content':'new value','overwrites_existing':True,'expected_exists':True,'expected_sha256':hashlib.sha256(b'old value').hexdigest()})
                with TestClient(main_module.app) as client:
                    response = client.post(f"/api/actions/{action['id']}", json={'decision':'approve'})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(target.read_text(encoding='utf-8'), 'new value')
                backups = list(backup_dir.glob('*.bak'))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_text(encoding='utf-8'), 'old value')
            finally:
                main_module.store, main_module.safe_path = old_store, old_safe
                if old_workspace is None: os.environ.pop('INDRA_WORKSPACE', None)
                else: os.environ['INDRA_WORKSPACE'] = old_workspace
                if old_backup is None: os.environ.pop('INDRA_BACKUP_DIR', None)
                else: os.environ['INDRA_BACKUP_DIR'] = old_backup
                if old_data is None: os.environ.pop('INDRA_DATA_DIR', None)
                else: os.environ['INDRA_DATA_DIR'] = old_data

if __name__ == '__main__': unittest.main()
