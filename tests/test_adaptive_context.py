import asyncio, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from app.agent import Agent
from app.store import Store
from app.harness import choose_profile, budget_for_task
from app.tools import build_context_pack

class AdaptiveContextTests(unittest.TestCase):
    def test_task_router_is_deterministic_and_bounded(self):
        with patch.dict(os.environ, {'INDRA_PROFILE':'auto','INDRA_MAX_STEPS':'6','INDRA_MAX_TOOL_CALLS':'9','INDRA_MAX_RUN_SECONDS':'90'}):
            self.assertEqual(choose_profile('quickly explain this'), 'fast')
            self.assertEqual(choose_profile('debug and fix the failing tests'), 'deep')
            budget = budget_for_task('debug and fix the failing tests')
            self.assertEqual(budget.profile, 'deep')
            self.assertEqual(budget.max_steps, 6)
            self.assertEqual(budget.max_tool_calls, 9)
            self.assertLessEqual(budget.max_duration_seconds, 90)
    def test_context_pack_excludes_dotenv_and_bounds_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('project overview', encoding='utf-8')
            (root / '.env').write_text('SECRET=do-not-read', encoding='utf-8')
            (root / 'main.py').write_text('print("hello")', encoding='utf-8')
            with patch('app.tools.ensure_workspace', return_value=root):
                pack = build_context_pack(max_chars=2000)
            self.assertIn('README.md', pack['files_included'])
            self.assertNotIn('.env', pack['files_included'])
            self.assertNotIn('do-not-read', pack['context'])
            self.assertLessEqual(pack['characters'], pack['character_budget'])

    def test_attached_context_is_bounded_labelled_untrusted_and_traced(self):
        class RecordingProvider:
            model = 'unit-test-model'
            _resolved_model = 'unit-test-model'
            def __init__(self): self.messages = None
            async def chat(self, messages, tools=None):
                self.messages = messages
                return {'role': 'assistant', 'content': 'evidence reviewed', 'tool_calls': []}
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'INDRA_DATA_DIR': temp}):
            store = Store()
            provider = RecordingProvider()
            result = asyncio.run(Agent(provider, store).run('Summarize this project', context='file excerpt\n' + ('x' * 15000)))
            user_message = [message for message in provider.messages if message.get('role') == 'user'][-1]['content']
            self.assertIn('Summarize this project', user_message)
            self.assertIn('UNTRUSTED WORKSPACE CONTEXT', user_message)
            self.assertIn('file excerpt', user_message)
            self.assertEqual(result['context_chars'], 12000)
            self.assertTrue(result['context_attached'])
            start_event = next(event for event in store.list_events(50) if event.get('type') == 'run_started')
            self.assertEqual(start_event['context_chars'], 12000)

if __name__ == '__main__': unittest.main()
