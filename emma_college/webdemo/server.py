"""Local web demo (stdlib only, 127.0.0.1 by default).

Two modes in one page:
  * "Tester une réponse"  paste any model reply and see what the harness does
  * "Discuter"            talk to a model (EMMA_BASE_URL / EMMA_MODEL) through it

Nothing is stored or logged: no conversation content is written anywhere.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..harness import Harness
from ..provider import from_env

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_BODY = 64 * 1024
_FALLBACK_PROFILES = [{"name": "default", "label_fr": "Standard", "label_en": "Standard"}]


def _profiles():
    try:
        from .. import access
        return [{"name": k, "label_fr": p.label_fr, "label_en": p.label_en}
                for k, p in access.PROFILES.items()]
    except Exception:
        return _FALLBACK_PROFILES


class Handler(BaseHTTPRequestHandler):
    provider = None
    server_version = "EmmaCollegeDemo/0.2"

    def log_message(self, *a):  # never log request content
        pass

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                         "script-src 'self' 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode())

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif self.path == "/api/profiles":
            self._json(200, {"profiles": _profiles(),
                             "provider": self.provider.name if self.provider else "none"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            return self._json(413, {"error": "too large"})
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._json(400, {"error": "bad json"})
        lang = req.get("lang") if req.get("lang") in ("fr", "en") else "fr"
        profile = str(req.get("profile") or "default")
        h = Harness(lang=lang, profile=profile)
        ex = {"statement": str(req.get("statement") or ""),
              "answer": (str(req["answer"]) if req.get("answer") else None)}
        student = str(req.get("student") or "")
        if self.path == "/api/check":
            res = h.check(student, str(req.get("reply") or ""), ex,
                          (str(req["attempt"]) if req.get("attempt") else None))
            return self._json(200, res.as_dict())
        if self.path == "/api/chat":
            pre = h.pre(student)
            if pre.block_model_call:
                return self._json(200, {"reply": pre.canned_reply,
                                        "verdicts": pre.verdicts, "spoken": None})
            msgs = [{"role": "system", "content": h.system_prompt()},
                    {"role": "user", "content": pre.message}]
            try:
                raw = self.provider.complete(msgs)
            except Exception as e:  # network / config problems are shown, not hidden
                return self._json(502, {"error": str(e)})
            res = h.check(student, raw, ex)
            d = res.as_dict()
            d["verdicts"] = pre.verdicts + [v for v in d["verdicts"] if v not in pre.verdicts]
            return self._json(200, d)
        self._json(404, {"error": "not found"})


def serve(host: str = "127.0.0.1", port: int = 8765):
    Handler.provider = from_env()
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"Emma Collège demo on http://{host}:{port}/  "
          f"(provider: {Handler.provider.name}; Ctrl-C to stop)")
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("WARNING: bound to a non-local address; this demo has no authentication.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print()
