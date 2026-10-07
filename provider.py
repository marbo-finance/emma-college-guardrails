"""Model-call interface expected by emma_layer.py — bring your own model.

emma_layer.py is provider-agnostic by design: it never assumes a specific
model's behaviour, and the guard/firewall logic (PII redaction, answer-leak
detection, safeguarding) does not call a model at all — it is pure,
deterministic text processing you can run and test with no model configured
(see bench/run_public_bench.py).

The ONLY place emma_layer.py touches a model is the single retry after a
detected answer leak (firewall_post's one retry call, with a reinforced
system prompt). That single call site is this module's `complete()`
function. This file is intentionally a stub, not a real integration: plug in
whatever inference backend you use (a hosted API, a local model server, a
provider router) by implementing `complete()` below. Nothing else in the
guard logic needs to change.

This is also, literally, the shape of our "model-agnostic" claim: the
pedagogical contract and the safety layer do not care which model answers,
as long as this one function returns text.
"""


def complete(messages, provider_config, vision=False):
    """Call a model and return (text, model_name, latency_ms).

    `messages` — a list of {"role": ..., "content": ...} dicts, OpenAI-style
        chat messages, ending with the system prompt rebuilt for the retry.
    `provider_config` — whatever your integration needs to pick a model/
        endpoint/credentials for this tenant (opaque to emma_layer.py; it is
        read verbatim from `tenant["provider"]` and passed through unchanged).
    `vision` — True if `messages` contains image content parts (attached
        exercise photo) that your backend must route to a vision-capable model.

    Reference implementation below is a no-op: it returns the system prompt's
    retry reminder unanswered, which is safe (firewall_post's second scan
    will not find a leak in it, so no exercise content would ever be
    exposed by this stub falling through). Replace this with your own
    inference call before using this module to drive a live product.
    """
    raise NotImplementedError(
        "provider.complete() is a stub — plug in your own model call here. "
        "See the module docstring: this is the single, intentionally narrow "
        "integration point emma_layer.py depends on."
    )
