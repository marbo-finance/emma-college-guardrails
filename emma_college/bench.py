"""Run the public corpus against the harness (no model, deterministic).

    python3 -m emma_college bench                 # default corpus
    python3 -m emma_college bench --corpus path.jsonl --json out.json

For each case:
  * every ``leaky_replies`` entry must be flagged (verdict ``block``)
  * every ``good_replies`` entry must NOT be flagged
  * every ``false_praise_replies`` entry must raise ``false_praise``
  * ``correct_attempt`` cases must never be blocked (the pupil already found it)
Cases tagged ``collision`` are reported separately: they document known
false-positive risks of any text-level rule, they are measured, not hidden.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

from .harness import Harness

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CORPUS = os.path.join(ROOT, "corpus", "emma-college-corpus.v0.2.jsonl")


def load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def run(path: str = DEFAULT_CORPUS, verbose: bool = False) -> dict:
    cases = load(path)
    stats = Counter()
    by_form = defaultdict(lambda: [0, 0])          # form -> [detected, total]
    by_obj = defaultdict(lambda: Counter())
    failures: list[dict] = []
    for c in cases:
        h = Harness(lang=c.get("lang", "fr"))
        ex = {"statement": c["exercise"], "answer": c["expected_answer"]}
        collision = "collision" in c.get("tags", [])
        attempt = c.get("student_attempt")
        for r in c.get("leaky_replies", []):
            res = h.check(c["student_message"], r["text"], ex, attempt)
            ok = "block" in res.verdicts
            by_form[r["form"]][1] += 1
            by_form[r["form"]][0] += ok
            stats["leak_total"] += 1
            stats["leak_detected"] += ok
            by_obj[c["objective_id"]]["leak_total"] += 1
            by_obj[c["objective_id"]]["leak_detected"] += ok
            if not ok:
                failures.append({"id": c["id"], "type": "missed_leak",
                                 "form": r["form"], "text": r["text"]})
        for r in c.get("good_replies", []):
            res = h.check(c["student_message"], r["text"], ex, attempt)
            blocked = "block" in res.verdicts
            key = "collision" if collision else "good"
            stats[f"{key}_total"] += 1
            stats[f"{key}_false_block"] += blocked
            by_obj[c["objective_id"]][f"{key}_total"] += 1
            by_obj[c["objective_id"]][f"{key}_false_block"] += blocked
            if blocked and not collision:
                failures.append({"id": c["id"], "type": "false_block",
                                 "form": r["form"], "text": r["text"],
                                 "masked": res.reply})
            if "false_praise" in res.verdicts and c.get("student_kind") != "wrong_attempt":
                stats["false_praise_on_good"] += 1
        for t in c.get("false_praise_replies", []):
            res = h.check(c["student_message"], t, ex, attempt)
            ok = "false_praise" in res.verdicts
            stats["praise_total"] += 1
            stats["praise_detected"] += ok
            if not ok:
                failures.append({"id": c["id"], "type": "missed_false_praise", "text": t})
    def rate(a, b):
        return None if not stats[b] else round(100.0 * stats[a] / stats[b], 1)
    summary = {
        "cases": len(cases),
        "leak_detection_pct": rate("leak_detected", "leak_total"),
        "false_block_pct": rate("good_false_block", "good_total"),
        "false_block_collision_pct": rate("collision_false_block", "collision_total"),
        "false_praise_detection_pct": rate("praise_detected", "praise_total"),
        "counts": dict(stats),
        "by_form": {k: {"detected": v[0], "total": v[1]} for k, v in sorted(by_form.items())},
        "by_objective": {k: dict(v) for k, v in sorted(by_obj.items())},
        "failures": failures,
    }
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="emma_college bench")
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--json", help="write the full report here")
    ap.add_argument("--min-leak", type=float, default=0.0,
                    help="fail if leak detection %% is below this")
    ap.add_argument("--max-false-block", type=float, default=100.0,
                    help="fail if false-block %% (non-collision) is above this")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    s = run(a.corpus, a.verbose)
    print(f"cases                     : {s['cases']}")
    print(f"leak detection            : {s['leak_detection_pct']} %  "
          f"({s['counts'].get('leak_detected', 0)}/{s['counts'].get('leak_total', 0)})")
    print(f"false blocks (good hints) : {s['false_block_pct']} %  "
          f"({s['counts'].get('good_false_block', 0)}/{s['counts'].get('good_total', 0)})")
    print(f"false blocks (collisions) : {s['false_block_collision_pct']} %  "
          f"({s['counts'].get('collision_false_block', 0)}/{s['counts'].get('collision_total', 0)})"
          "  <- known limit, tracked separately")
    print(f"false praise detection    : {s['false_praise_detection_pct']} %  "
          f"({s['counts'].get('praise_detected', 0)}/{s['counts'].get('praise_total', 0)})")
    for form, v in s["by_form"].items():
        print(f"   leak form {form:<16} {v['detected']}/{v['total']}")
    if a.verbose or s["failures"]:
        for f in s["failures"][:40]:
            print("  FAIL", f["id"], f["type"], f.get("form", ""), "|", f["text"][:90].replace("\n", " "))
        if len(s["failures"]) > 40:
            print(f"  ... {len(s['failures']) - 40} more (use --json)")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    bad = ((s["leak_detection_pct"] or 0) < a.min_leak
           or (s["false_block_pct"] or 0) > a.max_false_block)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
