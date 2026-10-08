"""The Emma Collège harness: deterministic checks around ANY model.

    h = Harness(lang="fr", profile="default")
    pre = h.pre(student_message)              # before calling a model
    res = h.check(student_message, model_reply,
                  exercise={"statement": "Résous 3x + 5 = 20.", "answer": "x=5"})
    res.reply      # safe text to show (leaks masked, PII redacted)
    res.verdicts   # ['block', 'pii_redact', 'human_review', 'false_praise']

No model is called here. ``emma_college.provider`` offers optional adapters.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import emma_layer as _legacy  # noqa: E402  (safeguarding / PII / smuggling rules)

from . import leak as _leak  # noqa: E402
from . import mathcore as _mc  # noqa: E402

_PRAISE = re.compile(
    r"\b(?:bravo|exact(?:e|ement)?|parfait(?:ement)?|excellent(?:e)?|super|génial|"
    r"bien joué|félicitations|très bien|c'est ça|tu as raison|c'est correct|"
    r"c'est juste|bonne réponse|tout à fait|great job|well done|exactly right|"
    r"that'?s correct|perfect|awesome|nice job)\b", re.IGNORECASE)

MAX_CHARS = 8000  # analysis cap: a tutor reply or pupil message is never this long;
# also bounds the cost of the legacy regex rules on hostile input.

_FALSE_PRAISE_HINT = {
    "fr": "Attention : ne félicite pas une réponse fausse ; corrige avec bienveillance.",
    "en": "Do not praise a wrong answer; correct it kindly.",
}


_NEGATION = re.compile(r"(?:\bpas|\bnon|\bpresque|\bjamais|\bplus|\bnot)\W*(?:\w+\W+){0,2}$",
                       re.IGNORECASE)


def has_praise(text: str) -> bool:
    """Praise words, ignoring negated uses ("pas tout à fait", "ce n'est pas ça")."""
    for m in _PRAISE.finditer(text or ""):
        if not _NEGATION.search(text[max(0, m.start() - 24):m.start()]):
            return True
    return False


@dataclass
class Pre:
    verdicts: list
    message: str
    block_model_call: bool
    canned_reply: Optional[str] = None


@dataclass
class Result:
    reply: str
    verdicts: list = field(default_factory=list)
    leaked: bool = False
    leaks: list = field(default_factory=list)
    raw_reply: str = ""
    spoken: Optional[str] = None
    findings: list = field(default_factory=list)
    mathml: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"reply": self.reply, "verdicts": self.verdicts,
                "leaked": self.leaked,
                "leaks": [{"text": l.text, "reason": l.reason} for l in self.leaks],
                "spoken": self.spoken,
                "findings": [getattr(f, "code", str(f)) for f in self.findings]}


def _answers_from(exercise: Optional[dict], student_message: str):
    if exercise and exercise.get("answer"):
        a = _leak.parse_answer(str(exercise["answer"]))
        if not a.empty:
            return [a], "given"
    guessed = []
    if exercise and exercise.get("statement"):
        guessed += _leak.guess_answers(exercise["statement"])
    guessed += _leak.guess_answers(student_message)
    return guessed, "guessed"


def _same_value(attempt: str, answers) -> Optional[bool]:
    """True/False if the pupil's attempt can be compared with a known answer,
    None if it cannot."""
    att = _leak.parse_answer(attempt or "")
    if att.empty or not answers:
        return None
    known = [a for a in answers if not a.empty]
    if not known:
        return None
    for a in known:
        for x in att.scalars:
            for y in a.scalars:
                if _mc.scalar_eq(x, y):
                    return True
                if a.percent and isinstance(y, type(x)) and _mc.scalar_eq(x, y * 100):
                    return True
        for p in att.polys:
            if any(p == q for q in a.polys):
                return True
    return False


class Harness:
    def __init__(self, lang: str = "fr", profile: str = "default", pii_redact: bool = True):
        self.lang = lang if lang in ("fr", "en") else "fr"
        self.profile = profile  # a built-in/registered name, or an access.Profile object
        self.tenant = {"language": self.lang,
                       "policy": {"pii_redact": pii_redact, "hints_not_answers": True}}

    def _adapted(self) -> bool:
        return bool(self.profile) and getattr(self.profile, "name", self.profile) != "default"

    # -- before the model ---------------------------------------------------
    def pre(self, student_message: str) -> Pre:
        student_message = (student_message or "")[:MAX_CHARS]
        r = _legacy.firewall_pre(student_message, self.tenant)
        return Pre(r["verdicts"], r["redacted_msg"], r["block_llm_call"], r["canned_reply"])

    def system_prompt(self) -> str:
        """The pedagogical contract + accessibility addendum for the profile."""
        text = _legacy.build_system_prompt(
            {"language": self.lang, "age_range": "13-15",
             "curriculum": "FR-cycle4 (4e/3e) mathématiques",
             "policy": {"hints_not_answers": True}})
        try:
            from . import curriculum
            text += "\n" + curriculum.prompt_addendum(self.lang)
        except Exception:
            pass
        if self._adapted():
            try:
                from . import access
                text += "\n" + access.profile_prompt_addendum(self.profile, self.lang)
            except Exception:
                pass
        return text

    # -- after the model ----------------------------------------------------
    def check(self, student_message: str, reply: str, exercise: Optional[dict] = None,
              attempt: Optional[str] = None) -> Result:
        reply = reply or ""
        student_message = (student_message or "")[:MAX_CHARS]
        res = Result(reply=reply[:MAX_CHARS], raw_reply=reply)
        if len(reply) > MAX_CHARS:
            res.verdicts.append("truncated")
        # 1. safeguarding content in the reply is withheld entirely
        if _legacy._SAFEGUARDING_RE.search(reply or ""):
            res.reply = (_legacy._CANNED_SAFEGUARDING_FR if self.lang == "fr"
                         else _legacy._CANNED_SAFEGUARDING_EN)
            res.verdicts.append("human_review")
            return res
        # 2. PII
        red, hit = _legacy.redact_pii(res.reply, self.tenant)
        if hit:
            res.reply = red
            res.verdicts.append("pii_redact")
        # 3. leak
        answers, origin = _answers_from(exercise, student_message)
        correct = _same_value(attempt, answers) if attempt else None
        statement = ((exercise or {}).get("statement") or "") + " " + (student_message or "")
        if correct is not True:
            leaks = _leak.find_leaks(res.reply, answers, statement)
            if not leaks and (_legacy._looks_like_answer_demand(student_message)
                              or not answers):
                for s in _legacy._extract_announced_answers(res.reply):
                    i = res.reply.find(s)
                    if i >= 0:
                        leaks.append(_leak.Leak(i, i + len(s), s, "announced"))
            if leaks:
                res.leaks = leaks
                res.leaked = True
                res.reply = _leak.mask(res.reply, leaks, self.lang)
                res.verdicts.append("block")
        # 4. false praise on a wrong attempt
        if correct is False and has_praise(res.reply):
            res.verdicts.append("false_praise")
        # 5. accessibility profile
        if self._adapted():
            try:
                from . import access
                ad = access.adapt(res.reply, self.profile, self.lang)
                res.findings = list(ad.findings)
                res.spoken = ad.spoken
                res.mathml = list(ad.mathml)
            except Exception:  # accessibility must never break the safety path
                pass
        return res
