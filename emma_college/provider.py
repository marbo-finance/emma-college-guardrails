"""Optional model adapters (bring your own model).

The harness itself never calls a model. These adapters exist so that a
teacher or a researcher can try the whole loop on their own machine:

* ``ScriptedProvider``      deterministic, no network (demo / tests)
* ``OpenAICompatProvider``  any OpenAI-compatible ``/v1/chat/completions``
                            endpoint: a local llama.cpp / vLLM server, a
                            hosted API, an institutional gateway.

Nothing here stores conversations. Configuration comes from environment
variables (never from files in the repository):

    EMMA_BASE_URL   e.g. http://127.0.0.1:8080/v1
    EMMA_MODEL      model name expected by the endpoint
    EMMA_API_KEY    optional bearer token
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Protocol


class Provider(Protocol):
    name: str

    def complete(self, messages: list[dict]) -> str: ...


class ScriptedProvider:
    """Returns canned replies in order: a safe hint, then a LEAKY reply,
    so the guard can be seen working with no model at all."""
    name = "scripted"

    def __init__(self, replies: list[str] | None = None):
        self.replies = replies or [
            "Pense à ce que tu dois faire pour isoler l'inconnue : "
            "quelle opération annule le « + 5 » ?",
            "La réponse est 5.",
            "Bravo, c'est exact !",
        ]
        self.i = 0

    def complete(self, messages: list[dict]) -> str:
        r = self.replies[self.i % len(self.replies)]
        self.i += 1
        return r


class OpenAICompatProvider:
    name = "openai-compatible"

    def __init__(self, base_url: str | None = None, model: str | None = None,
                 api_key: str | None = None, timeout: float = 60.0,
                 temperature: float = 0.3, max_tokens: int = 400):
        self.base_url = (base_url or os.environ.get("EMMA_BASE_URL", "")).rstrip("/")
        self.model = model or os.environ.get("EMMA_MODEL", "")
        self.api_key = api_key or os.environ.get("EMMA_API_KEY", "")
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        if not self.base_url or not self.model:
            raise ValueError("set EMMA_BASE_URL and EMMA_MODEL (OpenAI-compatible endpoint)")

    def complete(self, messages: list[dict]) -> str:
        body = json.dumps({"model": self.model, "messages": messages,
                           "temperature": self.temperature,
                           "max_tokens": self.max_tokens}).encode()
        req = urllib.request.Request(self.base_url + "/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        if self.api_key:
            req.add_header("Authorization", "Bearer " + self.api_key)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode())
        except (urllib.error.URLError, TimeoutError) as e:
            raise RuntimeError(f"model endpoint unreachable: {e}") from e
        return data["choices"][0]["message"]["content"] or ""


def from_env() -> Provider:
    if os.environ.get("EMMA_BASE_URL"):
        return OpenAICompatProvider()
    return ScriptedProvider()
