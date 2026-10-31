import io
import sys
import json
import urllib.error
from unittest.mock import patch
import http.server
import pathlib
import threading
import unittest
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import Handler

class AppServingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = Handler
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_application_assets_are_served(self):
        for path, marker in [('/', '文笺'), ('/app.js', 'localStorage'), ('/style.css', '@media')]:
            with self.subTest(path=path):
                with urllib.request.urlopen(f'http://127.0.0.1:{self.server.server_port}{path}') as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(marker, response.read().decode())

    def test_health_and_source_protection(self):
        with urllib.request.urlopen(f'http://127.0.0.1:{self.server.server_port}/api/health') as response:
            self.assertTrue(json.load(response)['ok'])
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(f'http://127.0.0.1:{self.server.server_port}/server.py')
        self.assertEqual(error.exception.code, 404)

    def test_ai_requires_configuration(self):
        with patch.dict('os.environ', {'MODEL_API_KEY':'', 'MODEL_NAME':'', 'MODEL_BASE_URL':''}):
            request = urllib.request.Request(f'http://127.0.0.1:{self.server.server_port}/api/ai', data=json.dumps({'mode':'summary','text':'研究摘录'}).encode(), headers={'Content-Type':'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            self.assertEqual(error.exception.code, 503)
            self.assertIn('MODEL_API_KEY', json.load(error.exception)['error'])

    def test_ai_success_uses_server_configuration(self):
        fake = io.BytesIO(json.dumps({'choices':[{'message':{'content':'摘要结果'}}]}).encode())
        local_open = urllib.request.urlopen
        with patch.dict('os.environ', {'MODEL_API_KEY':'test-only', 'MODEL_NAME':'test-model', 'MODEL_BASE_URL':'https://model.example/v1'}):
            with patch('server.urllib.request.urlopen', return_value=fake) as upstream:
                request = urllib.request.Request(f'http://127.0.0.1:{self.server.server_port}/api/ai', data=json.dumps({'mode':'summary','text':'研究摘录'}).encode(), headers={'Content-Type':'application/json'})
                with local_open(request) as response:
                    self.assertEqual(json.load(response)['text'], '摘要结果')
                sent = upstream.call_args.args[0]
                self.assertEqual(sent.full_url, 'https://model.example/v1/chat/completions')
                self.assertEqual(json.loads(sent.data)['model'], 'test-model')

    def test_ai_rejects_invalid_input(self):
        request = urllib.request.Request(f'http://127.0.0.1:{self.server.server_port}/api/ai', data=b'{}', headers={'Content-Type':'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 400)

if __name__ == '__main__':
    unittest.main()
