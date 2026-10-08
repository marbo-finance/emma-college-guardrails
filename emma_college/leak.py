"""Answer-leak detection for cycle-4 maths (4e / 3e).

Given the *final answer* of an exercise (or a best-effort guess computed from
the pupil's message) this module finds the places in a tutor reply that
state it — in any of the equivalent forms a pupil could read as "the
answer": ``5``, ``+5``, ``x = 5``, ``10/2``, ``6/8`` for ``3/4``, ``0,75``,
``75 %``, ``4√2`` for ``√32``, ``5,66`` (rounded), ``(x-3)(x+3)`` for
``x²-9``, ``treize``, LaTeX ``\\frac{3}{4}``, ``13 cm`` …

It is deterministic text processing, no model involved. It is a *risk
reducer, not a proof*: see README, section "Limits".

Public API
----------
``parse_answer(text) -> Answer``           machine-readable final answer
``guess_answers(student_message)``         answers computed from the question
``find_leaks(reply, answers, statement)``  list of ``Leak`` spans
``mask(reply, leaks, lang)``               reply with the spans masked
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Iterable, Optional

from . import mathcore as mc
from .words import find_number_words

MASK = {"fr": "〔réponse masquée — essaie d'abord !〕",
        "en": "〔answer masked — try it yourself first!〕"}

_UNIT_RE = re.compile(
    r"\s*(?:cm²|cm³|mm²|m²|m³|km|cm|mm|dm|kg|mg|ml|cl|dl|min|°C|°|€|"
    r"m/s|km/h|g|L|l|m|s|h)\s*$")
_REL = re.compile(r"<=|>=|≤|≥|=|<|>")


# ---------------------------------------------------------------------------
# answers
# ---------------------------------------------------------------------------

@dataclass
class Answer:
    raw: str
    scalars: list = field(default_factory=list)     # Fraction | Rad | Approx
    polys: list = field(default_factory=list)       # mc.Poly (degree >= 1)
    percent: bool = False
    inequality: Optional[str] = None
    source: str = "given"                           # given | guessed

    @property
    def empty(self) -> bool:
        return not self.scalars and not self.polys


def _split_parts(s: str) -> list[str]:
    s = s.strip()
    s = re.sub(r"^\s*S\s*=\s*", "", s)
    s = s.strip("{}[] ")
    parts = re.split(r"\s*(?:;|\bou\b|\bet\b)\s*", s)
    return [p for p in parts if p.strip()]


def parse_answer(text: str) -> Answer:
    """Parse a canonical final answer: ``'5'``, ``'3/4'``, ``'x=5'``,
    ``'x=2;x=-3'``, ``'x<=3'``, ``'4*sqrt(2)'``, ``'20%'``, ``'13 cm'``,
    ``'S={2;-3}'``, ``'x^2-9'``, ``'(x-3)(x+3)'``, ``'5*10^3'``."""
    ans = Answer(raw=text)
    for part in _split_parts(text):
        p = mc.normalize_math(part)
        m = re.match(r"^\s*([a-zA-Z])\s*(<=|>=|=|<|>)\s*(.+)$", p)
        if m:
            if m.group(2) != "=":
                ans.inequality = m.group(2)
            p = m.group(3)
        elif _REL.search(p):
            # e.g. "AB = 13 cm": keep the right-hand side
            p = _REL.split(p)[-1]
        p = p.strip()
        if p.endswith("%"):
            ans.percent = True
        p = _UNIT_RE.sub("", p) if not p.endswith("%") else p
        p = p.strip().rstrip(".")
        if not p:
            continue
        try:
            v = mc.evaluate(p, allow_var=True)
        except mc.Unsupported:
            continue
        if isinstance(v, mc.Poly):
            if v.is_const():
                ans.scalars.append(v.const_value())
            elif v.degree >= 1:
                ans.polys.append(v)
        else:
            ans.scalars.append(v)
    return ans


_CHUNK_RE = re.compile(r"[0-9a-zA-Z(\-−+√][0-9a-zA-Z\s+\-−×*/÷:^()=<>≤≥.,²³√%  ]*")
_MULT_X = re.compile(r"(?<=\d)\s*[xX]\s*(?=\d|\()")


def guess_answers(student_message: str) -> list[Answer]:
    """Best-effort: compute the answer of the arithmetic / fraction /
    first-degree-equation expression(s) found in the pupil's message.
    Silent (empty list) when nothing computable is found."""
    out: list[Answer] = []
    seen = set()
    for m in _CHUNK_RE.finditer(student_message or ""):
        chunk = m.group().strip()
        chunk = re.sub(r"[\s=?]+$", "", chunk)
        if len(chunk) < 3 or len(chunk) > 80:
            continue
        chunk = _MULT_X.sub("*", chunk)
        if not re.search(r"[-+*/×÷:^√−<>=]|sqrt", chunk):
            continue
        if re.search(r"[a-wyzA-WYZ]{2,}", chunk) and "sqrt" not in chunk:
            # prose, not maths ("combien fait ...")
            tail = re.search(r"[0-9(\-−+√][0-9a-zA-Z\s+\-−×*/÷:^()=<>≤≥.,²³√%]*$", chunk)
            if not tail:
                continue
            chunk = tail.group().strip()
        ans = Answer(raw=chunk, source="guessed")
        try:
            if _REL.search(mc.normalize_math(chunk)):
                op, bound = mc.solve_relation(chunk)
                if op in ("identity", "impossible"):
                    continue
                ans.scalars.append(bound)
                if op != "=":
                    ans.inequality = op
            else:
                v = mc.evaluate(chunk)
                s = v.const_value() if isinstance(v, mc.Poly) else v
                if isinstance(s, mc.Poly):
                    continue
                ans.scalars.append(s)
        except mc.Unsupported:
            continue
        key = tuple(str(x) for x in ans.scalars)
        if key and key not in seen:
            seen.add(key)
            out.append(ans)
    return out


# ---------------------------------------------------------------------------
# candidate extraction
# ---------------------------------------------------------------------------

_NUM = r"\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_TOKEN_RE = re.compile(
    r"(?P<lfrac>\\[dt]?frac\s*\{\s*(?P<lfn>[^{}]+?)\s*\}\s*\{\s*(?P<lfd>[^{}]+?)\s*\})"
    r"|(?P<rad>(?P<rc>\d+(?:[.,]\d+)?)?\s*(?:[*×]\s*)?(?:√|\\sqrt|sqrt)\s*"
    r"(?:\(\s*(?P<rr1>\d+)\s*\)|\{\s*(?P<rr2>\d+)\s*\}|(?P<rr3>\d+)))"
    r"|(?P<sci>(?P<sm>\d+(?:[.,]\d+)?)\s*(?:×|x|\*|·)\s*10\s*"
    r"(?:\^\s*\{?\s*(?P<se>[-−]?\d+)\s*\}?|(?P<sup>[⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)))"
    r"|(?P<frac>(?<![\w.,/])(?P<fs>[-−–]?)(?P<fn>\d+(?:[.,]\d+)?)\s*[/⁄]\s*"
    r"(?P<fd>\d+(?:[.,]\d+)?)(?![\d/]))"
    r"|(?P<num>(?<![\w.,^])(?P<ns>[-−–+]?)(?P<nv>" + _NUM + r"))"
)
_SUPMAP = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5",
           "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁻": "-"}
_ORDINAL_AFTER = re.compile(r"^(?:e|ème|eme|er|ère|ere|nd|nde)\b", re.IGNORECASE)
_RESULT_BEFORE = re.compile(
    r"(?:=|≈|≃|\best\b|\bvaut\b|\bdonc\b|\bsoit\b|\bégale?s?\b|\bégal(?:e|es)? à\b|"
    r"\btrouve\b|\brésultat\b|\bréponse\b|\bsolution\b|:|c'est|\bfait\b|\bdonne\b|"
    r"\bobtient\b|\bobtiens\b|\bavec\b la réponse)\s*(?:\*\*|«|\"|\$)?\s*$",
    re.IGNORECASE)


@dataclass
class Cand:
    start: int
    end: int
    text: str
    value: object          # Fraction | Rad | Approx
    kind: str              # num | frac | rad | sci | word | pct
    decimals: Optional[int] = None
    result_pos: bool = False
    pct: bool = False


def _num(s: str) -> Fraction:
    return Fraction(s.replace(" ", "").replace(" ", "").replace(" ", "")
                    .replace(",", "."))


def _sign(s: str) -> int:
    return -1 if s and s in "-−–" else 1


_RESULT_AFTER = re.compile(
    r"^\s*(?:\*\*|»|\")?\s*(?:est|sera|serait)\s+(?:la |le )?(?:solution|réponse|résultat|valeur)",
    re.IGNORECASE)


def _result_pos(reply: str, start: int, end: Optional[int] = None) -> bool:
    if _RESULT_BEFORE.search(reply[max(0, start - 30):start]):
        return True
    if end is not None:
        if _RESULT_AFTER.match(reply[end:end + 40]):
            return True
        ls = reply.rfind("\n", 0, start) + 1
        le = reply.find("\n", end)
        le = len(reply) if le < 0 else le
        if re.fullmatch(r"[\s*$>_\-]*", reply[ls:start]) and re.fullmatch(r"[\s*$.!]*", reply[end:le]) \
                and (ls > 0 or le < len(reply)):
            return True  # the value sits alone on its line
    return False


def extract_candidates(reply: str) -> list[Cand]:
    cands: list[Cand] = []
    for m in _TOKEN_RE.finditer(reply):
        s, e = m.start(), m.end()
        text = m.group()
        rp = _result_pos(reply, s, e)
        try:
            if m.group("lfrac"):
                n = mc.evaluate_scalar(m.group("lfn"))
                d = mc.evaluate_scalar(m.group("lfd"))
                if isinstance(n, Fraction) and isinstance(d, Fraction) and d != 0:
                    cands.append(Cand(s, e, text, n / d, "frac", None, rp))
            elif m.group("rad"):
                n = int(m.group("rr1") or m.group("rr2") or m.group("rr3"))
                coef = _num(m.group("rc")) if m.group("rc") else Fraction(1)
                v = mc._wrap(mc._rad_norm(coef, n))
                v = v.const_value() if isinstance(v, mc.Poly) else v
                cands.append(Cand(s, e, text, v, "rad", None, rp))
            elif m.group("sci"):
                exp = m.group("se") or "".join(_SUPMAP[c] for c in m.group("sup"))
                exp = int(exp.replace("−", "-"))
                v = _num(m.group("sm")) * (Fraction(10) ** exp)
                cands.append(Cand(s, e, text, v, "sci", None, rp))
            elif m.group("frac"):
                sign = _sign(m.group("fs"))
                d = _num(m.group("fd"))
                if d != 0:
                    cands.append(Cand(s, e, text, sign * _num(m.group("fn")) / d,
                                      "frac", None, rp))
            elif m.group("num"):
                sg = m.group("ns")
                if sg and s > 0 and (reply[s - 1].isalnum() or reply[s - 1] in ")]"):
                    # binary minus/plus glued to the previous operand: "3-5"
                    s2 = s + len(sg)
                    sign = 1
                    start = s2
                else:
                    sign = _sign(sg) if sg else 1
                    start = s
                if _ORDINAL_AFTER.match(reply[e:e + 5]):
                    continue
                if re.match(r"[xyznabckptXYZNABCKPT](?![A-Za-zÀ-ÿ])", reply[e:e + 2]):
                    continue  # coefficient glued to an unknown: "3x"
                line_start = reply.rfind("\n", 0, s) + 1
                if re.match(r"^\s*$", reply[line_start:s]) and re.match(r"[.)]\s", reply[e:e + 2]):
                    continue  # "1. étape" list numbering
                raw = m.group("nv")
                dec = len(re.split(r"[.,]", raw)[1]) if re.search(r"[.,]\d", raw) else 0
                rest = reply[e:e + 2].lstrip()
                pct = rest.startswith("%") or reply[e:e + 3].strip().startswith("%")
                val = sign * _num(raw)
                if pct:
                    val = val / 100
                cands.append(Cand(start, e, reply[start:e], val,
                                  "pct" if pct else "num", dec, rp, pct))
        except (mc.Unsupported, ValueError, ZeroDivisionError):
            continue
    # number words only in result position (avoids "deux étapes" noise)
    for s, e, v in find_number_words(reply):
        if (_result_pos(reply, s, e) or v.denominator != 1
                or re.search(r"\*\*\s*$", reply[max(0, s - 3):s])):
            cands.append(Cand(s, e, reply[s:e], v, "word", None, True))
    return cands


# ---------------------------------------------------------------------------
# statement exemption (verbatim quotes of the exercise are not leaks)
# ---------------------------------------------------------------------------

_NORM_MAP = {"−": "-", "–": "-", "×": "*", "·": "*", "÷": "/", ",": ".",
             "²": "^2", "³": "^3", "⁄": "/"}


def _norm_map(s: str) -> tuple[str, list[int]]:
    out, idx = [], []
    for i, ch in enumerate(s):
        if ch.isspace():
            continue
        rep = _NORM_MAP.get(ch, ch.lower())
        for c in rep:
            out.append(c)
            idx.append(i)
    return "".join(out), idx


def _in_statement(reply: str, start: int, end: int, nreply: str, idx: list[int],
                  nstatement: str) -> bool:
    if not nstatement:
        return False
    ns = next((k for k, i in enumerate(idx) if i >= start), None)
    ne = next((k for k, i in enumerate(idx) if i >= end), len(idx))
    if ns is None:
        return False
    for a in range(0, 6):
        for b in range(0, 6):
            if a + b < 2:
                continue
            lo, hi = ns - a, ne + b
            if lo < 0 or hi > len(nreply):
                continue
            if nreply[lo:hi] in nstatement:
                return True
    return False


# ---------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------

@dataclass
class Leak:
    start: int
    end: int
    text: str
    reason: str


def _scalar_match(c: Cand, a: Answer) -> Optional[str]:
    for av in a.scalars:
        pairs = [av]
        if a.percent and isinstance(av, Fraction):
            pairs = [av, av * 100]
        for target in pairs:
            if isinstance(c.value, Fraction) and isinstance(target, Fraction):
                if c.value == target:
                    if c.kind in ("frac", "sci") and not (
                            c.result_pos or target.denominator != 1):
                        # "15/3" for the integer 5 is usually a division
                        # instruction, not a stated result
                        continue
                    return "value" if c.kind in ("num", "pct", "word") else "equivalent"
                if (c.decimals and c.decimals >= 1 and c.kind == "num"
                        and abs(float(c.value) - float(target))
                        <= 0.5 * 10 ** -c.decimals + 1e-12
                        and (mc.terminating_decimals(target) is None
                             or mc.terminating_decimals(target) > c.decimals)):
                    return "rounded"
            elif isinstance(target, mc.Rad):
                if isinstance(c.value, mc.Rad) and c.value == target:
                    return "equivalent"
                if (isinstance(c.value, Fraction) and c.decimals
                        and c.decimals >= 2 and c.kind == "num"
                        and abs(float(c.value) - float(target))
                        <= 0.5 * 10 ** -c.decimals + 1e-12):
                    return "rounded"
            elif isinstance(target, mc.Approx):
                if abs(float(c.value) - float(target)) <= 5e-3 * max(1, abs(float(target))):
                    return "rounded"
    return None


_POLY_CHUNK = re.compile(r"[0-9x()+\-−×*/^²³.,\s]{3,}")


def _poly_leaks(reply: str, a: Answer, nreply: str, idx: list[int],
                nstatement: str) -> list[Leak]:
    out: list[Leak] = []
    for m in _POLY_CHUNK.finditer(reply):
        chunk = m.group()
        if "x" not in chunk and "X" not in chunk:
            continue
        lo, hi = m.start(), m.end()
        # trim non-expression edges, then try shrinking from both sides
        for left in range(0, min(6, len(chunk))):
            matched = False
            for right in range(len(chunk), max(left + 3, len(chunk) - 6), -1):
                sub = chunk[left:right].strip()
                if len(sub) < 3 or "x" not in sub.lower():
                    continue
                try:
                    p = mc.evaluate(sub.replace("X", "x"), allow_var=True)
                except mc.Unsupported:
                    continue
                if not isinstance(p, mc.Poly) or p.degree < 1:
                    continue
                if any(p == q for q in a.polys):
                    s0 = lo + left + (len(chunk[left:]) - len(chunk[left:].lstrip()))
                    e0 = s0 + len(sub)
                    if not _in_statement(reply, s0, e0, nreply, idx, nstatement) \
                            and not (len(sub) >= 3 and _norm_map(sub)[0] in nstatement):
                        out.append(Leak(s0, e0, reply[s0:e0], "polynomial"))
                    matched = True
                    break
            if matched:
                break
    return out


def _flatten_latex(t: str) -> str:
    """Length-preserving LaTeX flattening so spans still map onto the original:
    ``\\times``/``\\cdot`` -> ``×``/``·`` (padded), ``^{n}`` -> ``^n``."""
    t = re.sub(r"\\times", "×" + " " * 5, t)
    t = re.sub(r"\\cdot", "·" + " " * 4, t)
    t = re.sub(r"\^\{([^{}]{1,12})\}", lambda m: "^" + m.group(1) + " ", t)
    return t


def find_leaks(reply: str, answers: Iterable[Answer], statement: str = "") -> list[Leak]:
    """Spans of ``reply`` that state one of ``answers``.

    ``statement`` is the exercise text: verbatim quotes of it are exempt
    (a hint may restate the exercise)."""
    answers = [a for a in answers if a and not a.empty]
    if not reply or not answers:
        return []
    reply = _flatten_latex(reply)
    nreply, idx = _norm_map(reply)
    nstatement, _ = _norm_map(statement or "")
    leaks: list[Leak] = []
    cands = extract_candidates(reply)
    given = set()
    for gm in _TOKEN_RE.finditer(statement or ""):
        if gm.group("num"):
            try:
                given.add(_sign(gm.group("ns")) * _num(gm.group("nv")))
                given.add(_num(gm.group("nv")))
            except (ValueError, ZeroDivisionError):
                pass
    for c in cands:
        if c.kind == "num" and not c.result_pos and c.value in given:
            continue  # given data of the exercise, mentioned in passing
        for a in answers:
            if not a.scalars:
                continue
            reason = _scalar_match(c, a)
            if reason and c.kind == "word" and not c.result_pos:
                reason = None
            if reason and (c.result_pos
                           or not _in_statement(reply, c.start, c.end,
                                                nreply, idx, nstatement)):
                # The statement exemption protects verbatim quotes of the
                # exercise (a hint may restate it). A value stated in result
                # position ("est 10", "= 10") is an answer announcement, not a
                # quote, even when that value also occurs in the statement
                # (e.g. the answer of a mean equals one of the given data).
                leaks.append(Leak(c.start, c.end, c.text, reason))
                break
    for a in answers:
        if a.polys:
            leaks.extend(_poly_leaks(reply, a, nreply, idx, nstatement))
    # de-duplicate overlapping spans (keep the widest)
    leaks.sort(key=lambda l: (l.start, -(l.end - l.start)))
    merged: list[Leak] = []
    for l in leaks:
        if merged and l.start < merged[-1].end:
            if l.end > merged[-1].end:
                merged[-1] = Leak(merged[-1].start, l.end, reply[merged[-1].start:l.end],
                                  merged[-1].reason)
            continue
        merged.append(l)
    return merged


def mask(reply: str, leaks: Iterable[Leak], lang: str = "fr") -> str:
    tag = MASK.get(lang, MASK["fr"])
    out = reply
    for l in sorted(leaks, key=lambda x: x.start, reverse=True):
        out = out[:l.start] + tag + out[l.end:]
    return out
