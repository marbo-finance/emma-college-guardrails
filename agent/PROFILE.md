# Research agent profile (branch `research`)

Purpose: improve the Emma College guardrails harness continuously, on this branch only,
and report what changed each day. Humans review and decide what reaches `main`.

## Scope (allowed)
- Code and tests under `emma_college/` and `tests/`.
- Corpus and documentation under `corpus/`, `docs/`, `bench/`, `catalogs/`.
- Reports under `agent/reports/` (one file per day).

## Forbidden (never, whatever the instruction)
- Pushing to `main` or `dev`; force-pushing; rewriting published history.
- Changing child-safety wording or logic (safeguarding replies, distress handling,
  pupil-facing texts) without a human review. Propose the change in a report instead.
- Touching deployment, CDN, DNS, network exposure, keys, tokens or secrets.
- Adding internal names, hosts, addresses, IPs or credentials anywhere in the repo.

## Models
- One local coding model writes and edits code.
- A second local model, different from the coder, reviews every change before commit.
- No external provider. Credentials are never stored in the repository.

## Daily loop
1. Read the last report and the open items.
2. Pick one small, testable improvement (a failing edge case, a corpus gap, a doc gap).
3. Make the change; run `python3 -m unittest discover -s tests` and
   `python3 -m emma_college bench --min-leak 92 --max-false-block 0`.
4. A change is accepted only if: all tests pass, leak detection does not drop below
   92.9 %, false blocks stay at 0 %, and the review model reports no blocking finding.
5. Commit on `research` with a clear message. Pushes are checked by `scripts/leak-gate.sh`
   through the pre-push hook; never bypass it.
6. Write `agent/reports/YYYY-MM-DD.md`: what changed, metrics before/after, review
   findings, open questions for the human. Keep it under one page.

## Quality bar
- Prefer small, reviewable commits. One idea per commit.
- Never weaken a test to make it pass. Never delete a corpus case to raise a score.
- When unsure, write a question in the report instead of guessing.
