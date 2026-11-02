import unittest
from fastapi.testclient import TestClient
import app.main as main_module

class FakeAgent:
    async def run(self, message, history=None, event_sink=None, stream=False, context=None, mode="build", permission_requester=None, **kwargs):
        if event_sink:
            event_sink({'type':'token','text':'hello '})
            event_sink({'type':'token','text':'world'})
        result={'run_id':'r-test','answer':'hello world','status':'completed','duration_ms':1,'tool_calls':0,'steps':1,'trace':[],'profile':'fast'}
        if event_sink: event_sink({'type':'run_finished','run':result})
        return result

class StreamApiTests(unittest.TestCase):
    def test_stream_endpoint_emits_tokens_and_final_run(self):
        old = main_module.agent
        main_module.agent = FakeAgent()
        try:
            with TestClient(main_module.app) as client:
                response = client.post('/api/chat/stream', json={'message':'hello'})
            self.assertEqual(response.status_code, 200)
            self.assertIn('"type": "token"', response.text)
            self.assertIn('"type": "run_finished"', response.text)
            self.assertIn('hello world', response.text)
        finally:
            main_module.agent = old

if __name__ == '__main__': unittest.main()
