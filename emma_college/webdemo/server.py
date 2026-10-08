"""Local web demo (stdlib only, 127.0.0.1 by default).

Two modes in one page:
  * "Tester une réponse"  paste any model reply and see what the harness does
  * "Discuter"            talk to a model (EMMA_BASE_URL / EMMA_MODEL) through it

Nothing is stored or logged: no conversation content is written anywhere.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
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


class Gate:
    """Optional hosted-mode protection: bearer tokens (stored hashed), CORS
    allow-list, per-token rate limit and daily chat cap. Never logs content."""

    def __init__(self, tokens_file=None, cors_origin="", rate_per_min=30, chat_per_day=200):
        self.tokens = {}
        if tokens_file:
            with open(tokens_file, encoding="utf-8") as f:
                for t in json.load(f).get("tokens", []):
                    self.tokens[str(t["sha256"]).lower()] = str(t.get("label", ""))
            if not self.tokens:
                raise ValueError("tokens file has no token")
        self.required = bool(tokens_file)
        self.cors = cors_origin
        self.rate = rate_per_min
        self.chat_cap = chat_per_day
        self._hits = {}
        self._lock = threading.Lock()

    def who(self, header: str):
        """Key of a valid 'Bearer <token>' header, '' when auth is off, None if invalid."""
        if not self.required:
            return ""
        tok = header[7:].strip() if header.lower().startswith("bearer ") else ""
        digest = hashlib.sha256(tok.encode()).hexdigest()
        for known, label in self.tokens.items():
            if hmac.compare_digest(known, digest):
                return digest[:16]  # rate-limit key: unique per token, labels can repeat
        return None

    def allow(self, key: str, chat: bool = False) -> str:
        """'' if allowed, else 'rate' (per minute) or 'daily' (chat cap).
        ``chat=True`` counts one model call: call it only right before calling the model."""
        now = time.time()
        with self._lock:
            all_h, chat_h = self._hits.get(key, ([], []))
            all_h = [t for t in all_h if now - t < 60]
            chat_h = [t for t in chat_h if now - t < 86400]
            if len(all_h) >= self.rate:
                self._hits[key] = (all_h, chat_h)
                return "rate"
            if chat and len(chat_h) >= self.chat_cap:
                self._hits[key] = (all_h, chat_h)
                return "daily"
            all_h.append(now)
            if chat:
                chat_h.append(now)
            self._hits[key] = (all_h, chat_h)
            return ""


class Handler(BaseHTTPRequestHandler):
    provider = None
    gate = Gate()
    server_version = "EmmaCollegeDemo/0.3"
    timeout = 15  # seconds per socket read: slow or stalled clients free their thread

    def log_message(self, *a):  # never log request content
        pass

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self.gate.cors:
            self.send_header("Access-Control-Allow-Origin", self.gate.cors)
            self.send_header("Vary", "Origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                         "script-src 'self' 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode())

    def do_OPTIONS(self):  # CORS preflight
        self.send_response(204)
        if self.gate.cors:
            self.send_header("Access-Control-Allow-Origin", self.gate.cors)
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _auth(self):
        """Return the caller label, or None after having sent the error."""
        who = self.gate.who(self.headers.get("Authorization", ""))
        if who is None:
            self._json(401, {"error": "invalid or missing token"})
            return None
        return self._limit(who or "anon", False)

    def _limit(self, key, chat):
        why = self.gate.allow(key, chat)
        if why:
            self._json(429, {"error": "too many requests" if why == "rate"
                             else "daily chat limit reached", "reason": why})
            return None
        return key

    def do_GET(self):
        if self.path == "/api/health":
            return self._json(200, {"ok": True, "auth": self.gate.required,
                                    "chat": bool(self.provider and self.provider.name != "scripted")})
        if self.path in ("/", "/index.html"):
            if self.gate.required:  # the bundled page has no token field: hosted mode is API-only
                return self._json(404, {"error": "API only; use the web portal"})
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif self.path == "/api/profiles":
            if self._auth() is None:
                return
            self._json(200, {"profiles": _profiles(),
                             "provider": self.provider.name if self.provider else "none"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path not in ("/api/check", "/api/chat"):
            return self._json(404, {"error": "not found"})
        key = self._auth()
        if key is None:
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._json(400, {"error": "bad length"})
        if n < 0:
            return self._json(400, {"error": "bad length"})
        if n > MAX_BODY:
            return self._json(413, {"error": "too large"})
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._json(400, {"error": "bad json"})
        lang = req.get("lang") if req.get("lang") in ("fr", "en") else "fr"
        profile = str(req.get("profile") or "default")
        if isinstance(req.get("profile_def"), dict):  # teacher-built profile, nothing stored
            from .. import access
            try:
                profile = access.profile_from_dict(req["profile_def"])
            except access.ProfileFileError as e:
                return self._json(400, {"error": f"profile: {e}"})
        else:
            from .. import access
            if profile not in access.PROFILES:
                return self._json(400, {"error": "unknown profile"})
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
            if self._limit(key, True) is None:
                return
            try:
                raw = self.provider.complete(msgs)
            except Exception as e:  # network / config problems are shown, not hidden
                return self._json(502, {"error": str(e)})
            res = h.check(student, raw, ex)
            d = res.as_dict()
            d["verdicts"] = pre.verdicts + [v for v in d["verdicts"] if v not in pre.verdicts]
            return self._json(200, d)
        self._json(404, {"error": "not found"})


def serve(host: str = "127.0.0.1", port: int = 8765, tokens_file=None,
          cors_origin: str = "", rate: int = 30, chat_per_day: int = 200):
    Handler.provider = from_env()
    Handler.gate = Gate(tokens_file, cors_origin, rate, chat_per_day)
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"Emma Collège demo on http://{host}:{port}/  "
          f"(provider: {Handler.provider.name}; auth: {'tokens' if Handler.gate.required else 'off'}; "
          "Ctrl-C to stop)")
    if host not in ("127.0.0.1", "localhost", "::1") and not Handler.gate.required:
        print("WARNING: bound to a non-local address with no --tokens: no authentication.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print()
