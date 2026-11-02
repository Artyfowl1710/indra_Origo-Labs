import os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from app.tools import safe_path, propose_write, search_files
from app.store import Store

class ToolSafetyTests(unittest.TestCase):
 def test_path_escape_blocked(self):
  with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{"INDRA_WORKSPACE":d,"INDRA_DATA_DIR":d+"/data"}):
   import importlib, app.tools as tools; importlib.reload(tools)
   with self.assertRaises(ValueError): tools.safe_path("../escape.txt")
 def test_write_is_proposal_only(self):
  with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{"INDRA_WORKSPACE":d,"INDRA_DATA_DIR":d+"/data"}):
   import importlib, app.tools as tools, app.store as st; importlib.reload(st); importlib.reload(tools)
   store=st.Store(); result=tools.propose_write(store,"draft.txt","hello","test")
   self.assertEqual(result["status"],"approval_required"); self.assertFalse((Path(d)/"draft.txt").exists())
 def test_search(self):
  with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{"INDRA_WORKSPACE":d}):
   import importlib, app.tools as tools; importlib.reload(tools); (Path(d)/"a.txt").write_text("agent reliability")
   self.assertEqual(len(tools.search_files("reliability")["matches"]),1)
if __name__=="__main__": unittest.main()
