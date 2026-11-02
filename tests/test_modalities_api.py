import base64
import os
import tempfile
import unittest
from fastapi.testclient import TestClient

import app.main as main_module
from app.store import Store


class CaptureAgent:
    def __init__(self):
        self.attachment_context = None
        self.images = None
    async def run(self, message, history=None, event_sink=None, **kwargs):
        self.attachment_context = kwargs.get("attachment_context")
        self.images = kwargs.get("image_attachments")
        run = {"run_id":"attachment-test", "answer":"received", "status":"completed", "duration_ms":1,
               "tool_calls":0, "steps":1, "trace":[], "profile":"fast", "model":"test-model"}
        if event_sink:
            event_sink({"type":"run_finished", "run":run})
        return run


class ModalityApiTests(unittest.TestCase):
    def setUp(self):
        self.old_agent = main_module.agent
        self.old_store = main_module.store
        self.old_data_dir = os.environ.get("INDRA_DATA_DIR")
        self.temp = tempfile.TemporaryDirectory()
        os.environ["INDRA_DATA_DIR"] = self.temp.name
        main_module.store = Store()
        self.old_active = main_module.run_slots.active
        self.capture = CaptureAgent()
        main_module.agent = self.capture
        main_module.run_slots.active = 0
    def tearDown(self):
        main_module.agent = self.old_agent
        main_module.store = self.old_store
        main_module.run_slots.active = self.old_active
        if self.old_data_dir is None:
            os.environ.pop("INDRA_DATA_DIR", None)
        else:
            os.environ["INDRA_DATA_DIR"] = self.old_data_dir
        self.temp.cleanup()

    def test_capabilities_route(self):
        with TestClient(main_module.app) as client:
            response = client.get('/api/capabilities')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('voice_input', payload['modalities'])
        self.assertEqual(payload['modalities']['pdf_input']['ocr'], 'not_implemented')

    def test_text_attachment_reaches_agent_as_untrusted_context(self):
        with TestClient(main_module.app) as client:
            response = client.post('/api/chat', json={"message":"Summarize this", "attachments":[{
                "name":"notes.md", "mime_type":"text/markdown", "kind":"text", "text_content":"Results are preliminary."}]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('Results are preliminary.', self.capture.attachment_context)
        self.assertIn('UNTRUSTED CONTENT', self.capture.attachment_context)


    def test_image_payload_is_only_forwarded_after_attachment_validation(self):
        tiny_png = base64.b64encode(b"\x89PNG\r\n\x1a\nexample").decode("ascii")
        with TestClient(main_module.app) as client:
            response = client.post('/api/chat', json={"message":"Describe this chart", "attachments":[{
                "name":"chart.png", "mime_type":"image/png", "kind":"image", "data_base64":tiny_png}]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.capture.images), 1)
        self.assertTrue(self.capture.images[0]["data_url"].startswith("data:image/png;base64,"))

    def test_hosted_profile_refuses_missing_credentials_without_leaking_them(self):
        with TestClient(main_module.app) as client:
            response = client.get('/api/providers')
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertNotIn('INDRA_HOSTED_API_KEY', str(payload))
            # The fixture does not assume hosted credentials exist on the test machine.
            hosted = next(row for row in payload['profiles'] if row['id'] == 'hosted')
            self.assertNotIn('INDRA_HOSTED_API_KEY', str(payload))
            if not hosted['configured']:
                switched = client.post('/api/provider/profile', json={'profile':'hosted'})
                self.assertEqual(switched.status_code, 409)

    def test_scratchpad_round_trip_is_bounded_and_persistent(self):
        with TestClient(main_module.app) as client:
            saved = client.put('/api/scratchpad', json={'content':'Hypothesis: rank allocation depends on position.'})
            self.assertEqual(saved.status_code, 200, saved.text)
            loaded = client.get('/api/scratchpad')
        self.assertEqual(loaded.status_code, 200)
        self.assertIn('Hypothesis:', loaded.json()['content'])
        self.assertTrue(loaded.json()['persistent'])
        with TestClient(main_module.app) as client:
            bad = client.put('/api/scratchpad', json={'content':'x' * 30001})
        self.assertEqual(bad.status_code, 422)

    def test_bad_image_is_rejected_before_agent_run(self):
        before = self.capture.attachment_context
        with TestClient(main_module.app) as client:
            response = client.post('/api/chat', json={"message":"What is in this image?", "attachments":[{
                "name":"fake.png", "mime_type":"image/png", "kind":"image",
                "data_base64":base64.b64encode(b"not png").decode('ascii')}]})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.capture.attachment_context, before)


if __name__ == '__main__':
    unittest.main()
