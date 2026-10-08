# Contributing / Contribuer

Most useful contributions (EN/FR):

1. **A reply that should have been blocked but passed** (missed leak).
2. **A legitimate hint that was masked** (false block) — most important for pupils.
3. **Accessibility feedback** from teachers of visually impaired, dyslexic,
   neurodivergent pupils.
4. New corpus cases: add one entry to `corpus/build_corpus.py`, then
   `python3 corpus/build_corpus.py && python3 -m emma_college bench`.

Open an issue with: exercise, expected answer, pupil message, model reply,
verdict you expected. **Never include real pupil data.**
Rules: stdlib only, no network calls in the harness, tests must pass
(`python3 -m unittest discover -s tests`), no diagnosis inference.
Contributions are licensed Apache-2.0 (code) / CC BY 4.0 (data).
