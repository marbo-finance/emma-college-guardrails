import hashlib
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from emma_college.provider import ScriptedProvider
from emma_college.webdemo import server as S

TOKEN = "emma_test_token"


def _call(port, path, body=None, token=TOKEN, method=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                 data=None if body is None else json.dumps(body).encode(),
                                 method=method or ("POST" if body is not None else "GET"))
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"{}"), r.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), e.headers


class Hosted(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = tempfile.mkdtemp()
        f = os.path.join(d, "t.json")
        with open(f, "w") as fh:
            json.dump({"tokens": [{"label": "t", "sha256": hashlib.sha256(TOKEN.encode()).hexdigest()}]}, fh)
        S.Handler.provider = ScriptedProvider()
        S.Handler.gate = S.Gate(f, "https://emma.example", rate_per_min=1000, chat_per_day=2)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), S.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_health_is_public(self):
        c, d, h = _call(self.port, "/api/health", token=None)
        self.assertEqual(c, 200)
        self.assertTrue(d["auth"])

    def test_token_required(self):
        self.assertEqual(_call(self.port, "/api/check", {"reply": "x"}, token=None)[0], 401)
        self.assertEqual(_call(self.port, "/api/check", {"reply": "x"}, token="nope")[0], 401)
        self.assertEqual(_call(self.port, "/api/profiles", token=None)[0], 401)

    def test_check_masks_leak_and_cors(self):
        c, d, h = _call(self.port, "/api/check", {
            "statement": "Résous 3x + 5 = 20.", "answer": "x=5",
            "student": "donne la réponse", "reply": "La réponse est x = 5."})
        self.assertEqual(c, 200)
        self.assertIn("block", d["verdicts"])
        self.assertNotIn("5", d["reply"].replace("3x + 5", ""))
        self.assertEqual(h["Access-Control-Allow-Origin"], "https://emma.example")

    def test_profile_def_applies_and_is_not_registered(self):
        from emma_college import access
        pd = {"name": "classe-a", "label": "Classe A", "base": ["lecture_vocale"],
              "overrides": {"max_sentence_words": 8}}
        c, d, _ = _call(self.port, "/api/check", {"reply": "Calcule 3/4 + 1/4.", "profile_def": pd})
        self.assertEqual(c, 200)
        self.assertTrue(d["spoken"])
        self.assertNotIn("classe-a", access.PROFILES)

    def test_bad_profiles_rejected(self):
        bad = {"name": "TDAH_élève", "base": [], "overrides": {}}
        self.assertEqual(_call(self.port, "/api/check", {"reply": "x", "profile_def": bad})[0], 400)
        self.assertEqual(_call(self.port, "/api/check", {"reply": "x", "profile": "nope"})[0], 400)

    def test_chat_daily_cap_and_rate(self):
        codes = [_call(self.port, "/api/chat", {"student": "aide-moi", "statement": "3x+5=20"})[0]
                 for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])
        g = S.Gate(None, "", rate_per_min=2)
        self.assertEqual([g.allow("k", False) for _ in range(3)], ["", "", "rate"])

    def test_options_preflight(self):
        c, _, h = _call(self.port, "/api/check", token=None, method="OPTIONS")
        self.assertEqual(c, 204)
        self.assertIn("Authorization", h["Access-Control-Allow-Headers"])


if __name__ == "__main__":
    unittest.main()
