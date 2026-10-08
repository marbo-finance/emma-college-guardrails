# Emma Collège — a pedagogical harness for maths tutoring (grades 8–9, France)

[Version française → README.fr.md](README.fr.md)

A small, dependency-free Python library and test bench that wraps **any** LLM
used as a maths tutor for French *4e* and *3e* pupils (ages 13–15) and
**checks every reply deterministically** before a child sees it:

- **Hints, not answers** — the final answer to the exercise is detected by
  *mathematical equivalence*, not string matching (`6/8` ≡ `3/4` ≡ `0,75`;
  `x² + 6x + 9` ≡ `(x+3)²`; `5√2`; `4,5×10⁴`; "cinq"…) and masked.
- **No false praise** — "Bravo !" on a wrong attempt is flagged.
- **Child safety** — distress signals bypass the model and return a canned
  reply pointing to a trusted adult (119); personal data is redacted;
  instruction-smuggling through fake assistant turns is rejected.
- **Model-agnostic** — no model is called by the harness; bring your own
  (local llama.cpp/vLLM, hosted API, institutional gateway).
- **Accessibility as preferences, never diagnoses** — see below.

> Status: **v0.2, research prototype.** Not teacher-validated yet, no
> accessibility audit, heuristics rather than proofs. Limits are listed
> up-front below. Published by MARBO FINANCE (Massy) as the public part of an
> Édu-Up application (call planned for March 2027).

## Try it in 10 minutes (teachers)

Requires Python ≥ 3.10. No install, no account, no key, no network.

```bash
git clone https://github.com/marbo-finance/emma-college-guardrails && cd emma-college-guardrails
python3 -m emma_college serve          # local test bench: http://127.0.0.1:8765
```

Type an exercise and its expected answer, paste a model reply (or let the
scripted demo answer) and see what the harness masks, why, and in which
verdict. Everything stays on your machine; nothing is logged.

From the command line:

```bash
python3 -m emma_college check --exercise "Résous 3x + 5 = 20." --answer "x=5" \
    --student "donne-moi la réponse" --reply "La solution est x = 5."
python3 -m emma_college chat --exercise "Résous 3x + 5 = 20." --answer "x=5"
python3 -m emma_college speak "x² + 6x + 9 = (x+3)²"     # spoken maths for screen readers
```

To use a real model, set `EMMA_BASE_URL`, `EMMA_MODEL` (and `EMMA_API_KEY` if
needed) for any OpenAI-compatible endpoint. What we would like from you:
wrong blocks, missed leaks, wording a pupil would find odd — see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Reproduce the measurements (researchers)

```bash
python3 -m emma_college bench                 # 4e/3e corpus v0.2 (30 cases), no model
python3 -m emma_college bench --json out.json # full per-case report
python3 bench/run_public_bench.py             # legacy generic bench: 42/42
python3 -m unittest discover -s tests         # unit tests (≈100, incl. 75 for accessibility)
```

Current results on `corpus/emma-college-corpus.v0.2.jsonl` (hand-written by
the authors — **not** an independent benchmark):

| Measure | Result |
|---|---|
| Leaky replies detected | 92.9 % (52/56) |
| False blocks on legitimate hints | 0 % (0/31) |
| False praise on wrong attempts detected | 100 % (3/3) |

Known misses are printed, not hidden: a final answer written as a word next
to a unit (*"Soixante euros."*), a result that coincides with a number given
in the statement, exact values with π (`36π`), and English number words.
Cases tagged `collision` document text-level false-positive risks and are
reported separately. Corpus format and annotation protocol:
[docs/CORPUS.md](docs/CORPUS.md). We are looking for **2–3 researchers**
(didactics of mathematics, EIAH/tutoring, accessibility) to challenge the
corpus and the metrics.

## Works with any LLM

The harness sits **after** the model, so it does not care which one you use.
Anything reachable through an OpenAI-compatible `/v1/chat/completions`
endpoint works with the bundled adapter, which includes a
[LiteLLM](https://github.com/BerriAI/litellm) proxy in front of:

- **open-source models hosted locally** — by a school, on a teacher's
  workstation or on the pupil's own PC (llama.cpp, vLLM, LM Studio…);
- **sovereign / European models** (e.g. Mistral);
- **well-known commercial models** (e.g. Claude, OpenAI, Gemini).

Set `EMMA_BASE_URL` / `EMMA_MODEL` (and `EMMA_API_KEY`). The checks are the
same whatever the model; only the pupil-data exposure differs, and that choice
belongs to the integrator (a local or in-school model keeps pupil text on
site; a hosted API does not — mind GDPR and the ministry's AI usage
framework). *Honesty note:* we have run the full loop with the scripted
provider and measured the checks on fixed replies; per-model leak rates are
not yet published — running the bench on your model of choice is one of the
things we would like researchers to do.

## Hosted trial server (no install for testers)

For teachers and researchers who should not install anything, run the same demo as a token-gated API and let
a static page call it (see `emma.talki-app.fr/testeurs.html`):

```bash
python3 -m emma_college token "jane-doe" --file tokens.json     # prints the token once; only its hash is stored
python3 -m emma_college serve --tokens tokens.json --cors-origin https://your.site --rate 30 --chat-per-day 200
```

Bearer-token auth (hashed at rest), one allowed CORS origin, per-token rate and daily model-call caps, no content
logged. Teacher-built pupil profiles are sent inline per request and never stored. Put it behind HTTPS yourself.

## Pupil profile files (teachers)

A teacher can describe a group of pupils by **needs and preferences** (never by condition) in a small JSON file — the
[Emma portal](https://emma.talki-app.fr/en/pupil-profiles.html) has a builder, or write it by hand:

```json
{"schema": "emma-pupil-profile/1",
 "profiles": [{"name": "group-a", "label": "Group A: voice + one step",
               "base": ["lecture_vocale", "une_etape_a_la_fois"],
               "overrides": {"max_sentence_words": 10}}]}
```

```bash
python3 -m emma_college serve --profiles my-profiles.json     # then pick it in the bench
python3 -m emma_college check --profiles my-profiles.json --profile group-a --reply "..." ...
```

Labels that look like a diagnosis or health term are **refused** (GDPR art. 9), unknown fields are refused, nothing is stored.

## What makes this different

Édu-Up already supported socratic maths tutors (e.g. DinoBot, which states
that its AI guides by questioning without giving the answer). We make **no
claim** that others lack protections; their code is not public so we cannot
compare. What this repository adds, and what you can verify yourself:

1. **Executable and open** — rules, equivalence engine, corpus and bench are
   public and run offline. Of the Édu-Up laureates and French open-source maths tutors we looked at,
   none publishes comparable code ([docs/COMPARISON.md](docs/COMPARISON.md), with sources and limits).
2. **Grade 8–9 curriculum-aligned test corpus** — 29 objectives
   (`catalogs/emma-college-4e-3e.v1.json`) covering relative numbers,
   literal calculus, equations, Pythagoras/Thalès, trigonometry, remarkable
   identities, roots, scientific notation, probabilities, functions.
3. **Exact-equivalence leak detection** — fractions, decimals with French
   comma, radicals, polynomials, percents, inequalities; leaves the pupil's
   own correct answer alone.
4. **Disability is a first-class requirement, not a footnote** (below).
5. **Honest limits** and a bench that prints its own failures.

## Accessibility and disability

What the harness does:

- **Needs-based preference profiles**, never diagnoses (health data is
  special-category under GDPR art. 9): e.g. short sentences, no
  metaphors, spoken-maths output, large-print friendly structure, reduced
  cognitive load, step-by-step pacing. A teacher or parent picks preferences;
  the system never infers or stores a condition.
- **Deterministic text lint/adaptation** of tutor replies for each profile.
- **Spoken maths in French and English** (`speak`) and **MathML export** for
  screen readers and braille displays.
- **Braille is delegated**, not reinvented: use MathCAT, Liblouis or apiDV's
  MathsDV tooling with the MathML we export.

What it does **not** do: it is not a user interface. WCAG/RGAA conformance of
a pupil-facing app is the integrator's job, and **we claim no RGAA audit or
compliance**. The local test bench is built with semantic HTML, labels and
keyboard operation as a sanity baseline only. Details and open questions:
[docs/ACCESSIBILITY.md](docs/ACCESSIBILITY.md). We are actively seeking
teachers who work with visually impaired, dyslexic or neurodivergent pupils.

## Limits, stated up-front

- Leak detection is heuristic text analysis, not a second-model judgement or
  a proof. It lowers risk; it does not remove it.
- Equivalence works on answers the engine can parse; unparsed answers fall
  back to the older announced-answer rules.
- The corpus is small, author-written and not teacher-validated.
- The catalogue follows the current cycle 4 programme (2019). New programme
  (order of 18 Feb 2026): 5e in 2026-27, **4e in 2027-28**, 3e in 2028-29;
  the catalogue will be revised when detailed texts are available.
- Very small answers (0, 1) are hard to protect: any mention of that digit outside the statement is masked (false-block risk, found in review).
- LaTeX is only partly handled (`\times`, `^{n}`); other macros are not.
- Server-side concerns (history injection, multi-tenant routing) are outside
  this repository.

## Layout

| Path | Content |
|---|---|
| `emma_college/` | harness, leak engine, exact maths, CLI, local web bench |
| `emma_layer.py` | original safeguarding / PII / smuggling rules |
| `corpus/` | 4e/3e test corpus (CC BY 4.0) + builder |
| `catalogs/` | curriculum objective catalogues (CC BY 4.0) |
| `bench/` | legacy generic bench and round-6 results |
| `docs/` | comparison, corpus protocol, accessibility |
| `tests/` | unit tests |

## Cite / licence

Code: **Apache-2.0**. Data (corpus, catalogues, bench): **CC BY 4.0**. See
`CITATION.cff` to cite. Questions and test reports are welcome by issue.
