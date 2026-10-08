"""French number words -> exact values (0 .. 999 999) and simple fractions.

Used only to catch leaks written in letters ("la réponse est treize",
"trois quarts"). Deliberately conservative: the bare articles "un"/"une" are
never read as numbers.
"""
from __future__ import annotations

import re
import unicodedata
from fractions import Fraction

_UNITS = {
    "zero": 0, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4,
    "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
    "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15,
    "seize": 16,
}
_TENS = {"vingt": 20, "vingts": 20, "trente": 30, "quarante": 40,
         "cinquante": 50, "soixante": 60}
_FRAC_DEN = {"demi": 2, "demie": 2, "demis": 2, "demies": 2, "tiers": 3,
             "quart": 4, "quarts": 4}
_ORD_DEN = {"cinquieme": 5, "sixieme": 6, "septieme": 7, "huitieme": 8,
            "neuvieme": 9, "dixieme": 10, "centieme": 100, "millieme": 1000}

_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ]+(?:-[A-Za-zÀ-ÿ]+)*")


def _ascii(w: str) -> str:
    return unicodedata.normalize("NFD", w.lower()).encode("ascii", "ignore").decode()


def _atoms(token: str):
    """Split a hyphenated token into atoms; None if any atom is unknown."""
    atoms = []
    for part in token.split("-"):
        a = _ascii(part)
        if a in _UNITS or a in _TENS or a in ("dix", "cent", "cents", "mille",
                                               "et", "quatre", "vingt"):
            atoms.append(a)
        else:
            return None
    return atoms


def _value(atoms: list[str]) -> int | None:
    """Evaluate a sequence of French number atoms."""
    total, cur = 0, 0
    i = 0
    if not atoms:
        return None
    seq = [a for a in atoms if a != "et"]
    # quatre-vingt(s) / soixante-dix / quatre-vingt-dix
    merged: list[int | str] = []
    while i < len(seq):
        a = seq[i]
        if a == "quatre" and i + 1 < len(seq) and seq[i + 1] in ("vingt", "vingts"):
            merged.append(80)
            i += 2
            continue
        merged.append(_UNITS.get(a, _TENS.get(a, a)) if a not in ("cent", "cents", "mille") else a)
        i += 1
    for tok in merged:
        if isinstance(tok, int):
            if tok == 0 and len(merged) > 1:
                return None
            cur += tok
        elif tok in ("cent", "cents"):
            cur = (cur or 1) * 100
        elif tok == "mille":
            total += (cur or 1) * 1000
            cur = 0
        else:
            return None
    return total + cur


def find_number_words(text: str):
    """Yield (start, end, Fraction) for number words found in ``text``.

    Handles integers up to 999 999, "x virgule y", "<n> demi(s)/tiers/quart(s)/
    cinquièmes…", and "<n> sur <m>".
    """
    tokens = [(m.start(), m.end(), m.group()) for m in _WORD_RE.finditer(text)]
    out = []
    i = 0
    while i < len(tokens):
        s, e, tok = tokens[i]
        atoms = _atoms(tok)
        if atoms is None or atoms == ["et"]:
            i += 1
            continue
        # extend over following atom tokens (separated by spaces)
        j = i
        chain = list(atoms)
        end = e
        while j + 1 < len(tokens):
            ns, ne, nt = tokens[j + 1]
            if text[end:ns].strip() != "":
                break
            na = _atoms(nt)
            if na is None:
                break
            chain += na
            end = ne
            j += 1
        # strip a trailing/leading 'et'
        while chain and chain[0] == "et":
            chain.pop(0)
            s = tokens[i][0]
        while chain and chain[-1] == "et":
            chain.pop()
        val = _value(chain)
        i = j + 1
        if val is None:
            continue
        if chain in (["un"], ["une"]):
            # bare article: only keep if followed by a fraction word
            pass
        frac = Fraction(val)
        span_end = end
        # fraction words / 'virgule' / 'sur' after the integer
        if i < len(tokens):
            ns, ne, nt = tokens[i]
            nl = _ascii(nt)
            if text[end:ns].strip() == "":
                if nl in _FRAC_DEN or nl.rstrip("s") in _ORD_DEN:
                    den = _FRAC_DEN.get(nl) or _ORD_DEN[nl.rstrip("s")]
                    frac = Fraction(val, den)
                    span_end = ne
                    i += 1
                elif nl == "virgule" and i + 1 < len(tokens):
                    ds, de, dt = tokens[i + 1]
                    da = _atoms(dt)
                    dv = _value(da) if da else None
                    if dv is not None:
                        digits = len(str(dv))
                        frac = Fraction(val) + Fraction(dv, 10 ** digits)
                        span_end = de
                        i += 2
                elif nl == "sur" and i + 1 < len(tokens):
                    ds, de, dt = tokens[i + 1]
                    da = _atoms(dt)
                    dv = _value(da) if da else None
                    if dv:
                        frac = Fraction(val, dv)
                        span_end = de
                        i += 2
        if chain in (["un"], ["une"]) and frac.denominator == 1:
            continue  # bare article, not a number
        out.append((s, span_end, frac))
    return out
