# How Emma Collège relates to existing work

*Last checked: 2026-10-08. Sources are public pages; "to verify" means we could not confirm a point and we do not claim it. Corrections are welcome (open an issue).*

Emma Collège is **not** a tutoring product. It is the open, testable **rules layer** that sits between any language model and a 13–15-year-old pupil in French maths (4e/3e): never state the final answer, never praise a wrong answer, never let personal data through, hand over to a trusted adult on distress, and adapt the *presentation* to the pupil's needs without ever recording a diagnosis.

## What we found (and what we do not claim)

| Project | Who | Public code | What it does | Relation to Emma Collège |
|---|---|---|---|---|
| DinoBot | OuiActive (Édu-Up 01/2025) | none verified for the product | Socratic AI for maths, grade 6 to BTS; "guides without giving the answer" | Closest in intent. Its guard mechanism is not publicly documented, **so we make no claim that it lacks leak detection**. Our difference is *verifiability*: rules and tests are public. |
| MATHIA, Adaptiv'Math, Smart Enseigno | P2IA programme | no; the ministry stated it will not publish the code of P2IA assistants (cycle 3) | adaptive tutors, cycles 2–3 | Complementary; different level (4e/3e) and not open. |
| MathPower, Édumalin | Édu-Up laureates | none verified | diagnostic / individualised practice | Different object (no dialogue). |
| AccessDoc | INKLUDO (Édu-Up 04/2024) | none verified | accessible documents, maths in LaTeX | Complementary (documents, not tutoring). |
| MathALÉA, Labomep/Sésaparcours, MathGraph32 | Coopmaths, Sésamath | yes, AGPL-3.0 | exercise generation, practice, geometry | Natural sources of exercises. Coupling code needs licence care (AGPL vs Apache-2.0); exchanging *data* is simpler. |
| OATutor | UC Berkeley CAHLR | yes, MIT | open intelligent tutor with pre-written content | Different approach (authored content, not an LLM behind guardrails). Not French / not aligned with the French programme (to verify). |
| MathTutorBench | ETH Zürich | yes, CC BY 4.0 | benchmark of LLM tutor pedagogy (English) | Measures the *model*. Ours measures a deterministic *rules layer*, in French, tied to the 4e/3e programme. |
| tutor-robustness-eval | EPFL ML4ED | yes (no licence declared) | adversarial pupils extracting answers, simple defences | Research we build on conceptually; we do not claim priority. |
| MathCAT, Liblouis | DAISY, liblouis | yes, MIT / LGPL | speech, braille, navigation for maths | We **delegate** braille/navigation to these tools rather than reinvent them. |

## What we think is genuinely different (and how you can check it)

1. **A public, executable test corpus in French on the 4e/3e programme.** `corpus/` holds hundreds of cases, each tied to an objective of `catalogs/emma-college-4e-3e.v1.json`, with leaking and legitimate replies. `python3 -m emma_college bench` reproduces every number we publish. We found no comparable French corpus; absence of evidence is not evidence of absence, so tell us if one exists.
2. **Exact-equivalence leak detection** (fractions, relative numbers, equations, radicals, expanded/factorised forms, rounding), not only "does the literal appear". See the coverage matrix in the README.
3. **Disability handling designed as preferences, not diagnoses** (GDPR art. 9), with deterministic text checks and a speech-ready rendering of maths. See `docs/ACCESSIBILITY.md`.
4. **Model-agnostic by construction**: no provider code in the safety path.

## What it is not

Not a proof of safety, not an RGAA audit, not validated by practising teachers yet (v0.2). See *Limits* in the README.
