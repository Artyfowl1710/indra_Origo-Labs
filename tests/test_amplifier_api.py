import unittest
from fastapi.testclient import TestClient
from app.main import app

class AmplifierApiTests(unittest.TestCase):
    def test_status_exposes_honest_feature_state(self):
        with TestClient(app) as client:
            response = client.get('/api/amplifier/status')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['features']['best_of_n'], 'scaffold only')

    def test_valid_plan_endpoint(self):
        payload = {"plan":{"goal":"sum numbers","steps":[{"id":"calc","type":"compute","instruction":"Compute 2+2","verifier":"numeric"}]}}
        with TestClient(app) as client: response = client.post('/api/amplifier/plan/validate', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['valid'])

    def test_invalid_plan_endpoint_is_422(self):
        with TestClient(app) as client: response = client.post('/api/amplifier/plan/validate', json={"plan":{"goal":"x","steps":[]}})
        self.assertEqual(response.status_code, 422)

    def test_context_pack_endpoint(self):
        with TestClient(app) as client:
            response = client.post('/api/amplifier/context/pack', json={"token_budget":10,"items":[{"source":"a","relevance":1,"text":"small context"}]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertLessEqual(response.json()['estimated_tokens'], 10)

    def test_verifier_endpoint(self):
        with TestClient(app) as client: response = client.post('/api/amplifier/verify', json={"verifier":"numeric","result":42,"expected":42})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'pass')

    def test_arithmetic_verify_endpoint(self):
        with TestClient(app) as client:
            response = client.post('/api/amplifier/verify/arithmetic', json={"expression":"6*7","claimed":42})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'pass')

    def test_token_estimate_discloses_not_exact(self):
        with TestClient(app) as client: response = client.post('/api/amplifier/tokens/estimate', json={"text":"abcd"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['exact'])

if __name__ == '__main__': unittest.main()
