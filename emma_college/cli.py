"""Command line: ``python3 -m emma_college <command>``.

    bench     run the public corpus (no model)
    check     test ONE model reply: --student "..." --reply "..." [--answer x=5]
    chat      talk to a model through the harness (needs EMMA_BASE_URL/EMMA_MODEL,
              otherwise a scripted demo provider is used)
    speak     print the spoken form of a maths text (for screen readers / TTS)
    serve     local web demo for teachers and researchers (127.0.0.1 only)
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__


def _cmd_check(a) -> int:
    from .harness import Harness
    h = Harness(lang=a.lang, profile=a.profile)
    ex = {"statement": a.exercise or "", "answer": a.answer}
    res = h.check(a.student, a.reply, ex, a.attempt)
    if a.json:
        print(json.dumps(res.as_dict(), ensure_ascii=False, indent=2))
    else:
        print("verdicts:", res.verdicts or "none (reply passes)")
        print("reply   :", res.reply)
        if res.spoken:
            print("spoken  :", res.spoken)
        for f in res.findings:
            print("finding :", getattr(f, "code", f), "-",
                  getattr(f, "message_" + a.lang, ""))
    return 0 if "block" not in res.verdicts else 2


def _cmd_chat(a) -> int:
    from .harness import Harness
    from .provider import from_env
    h = Harness(lang=a.lang, profile=a.profile)
    prov = from_env()
    print(f"[provider: {prov.name}] — Ctrl-D pour quitter / to quit")
    history = [{"role": "system", "content": h.system_prompt()}]
    ex = {"statement": a.exercise or "", "answer": a.answer}
    while True:
        try:
            msg = input("élève> " if a.lang == "fr" else "pupil> ")
        except EOFError:
            print()
            return 0
        pre = h.pre(msg)
        if pre.block_model_call:
            print("emma>", pre.canned_reply)
            continue
        history.append({"role": "user", "content": pre.message})
        raw = prov.complete(history)
        res = h.check(msg, raw, ex)
        history.append({"role": "assistant", "content": res.reply})
        print("emma>", res.reply, f"   {res.verdicts or ''}")


def _cmd_speak(a) -> int:
    from . import access
    print(access.spoken_math(a.text, a.lang))
    return 0


def _cmd_serve(a) -> int:
    from .webdemo.server import serve
    serve(a.host, a.port)
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "bench":
        from .bench import main as bench_main
        return bench_main(argv[1:])
    ap = argparse.ArgumentParser(prog="emma_college",
                                 description="Emma Collège — pedagogical harness")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bench", help="run the corpus against the harness")
    b.add_argument("rest", nargs=argparse.REMAINDER)

    c = sub.add_parser("check", help="test one model reply")
    c.add_argument("--student", required=True)
    c.add_argument("--reply", required=True)
    c.add_argument("--exercise", default="")
    c.add_argument("--answer", default=None, help="expected final answer, e.g. x=5, 3/4")
    c.add_argument("--attempt", default=None, help="pupil's attempt, if any")
    c.add_argument("--lang", default="fr", choices=["fr", "en"])
    c.add_argument("--profile", default="default")
    c.add_argument("--json", action="store_true")

    ch = sub.add_parser("chat", help="interactive chat through the harness")
    ch.add_argument("--exercise", default="")
    ch.add_argument("--answer", default=None)
    ch.add_argument("--lang", default="fr", choices=["fr", "en"])
    ch.add_argument("--profile", default="default")

    s = sub.add_parser("speak", help="spoken form of a maths text")
    s.add_argument("text")
    s.add_argument("--lang", default="fr", choices=["fr", "en"])

    sv = sub.add_parser("serve", help="local web demo")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8765)

    for sp in (c, ch, sv):
        sp.add_argument("--profiles", help="JSON file of pupil profiles (schema emma-pupil-profile/1)")
    a = ap.parse_args(argv)
    if getattr(a, "profiles", None):
        from . import access
        try:
            loaded = access.load_profiles_file(a.profiles)
        except access.ProfileFileError as e:
            print(f"profiles: {e}", file=sys.stderr)
            return 2
        print(f"profiles loaded: {', '.join(loaded)}", file=sys.stderr)
    if a.cmd == "bench":
        from .bench import main as bench_main
        return bench_main(a.rest)
    return {"check": _cmd_check, "chat": _cmd_chat, "speak": _cmd_speak,
            "serve": _cmd_serve}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
