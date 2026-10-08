"""Accessibility layer for Emma Collège: needs-based presentation profiles.

Deterministic, stdlib-only. Checks and transforms TEXT. UI-level accessibility
(focus, contrast, keyboard, ARIA) belongs to the integrating interface and its
RGAA 4.1 / WCAG 2.2 AA audit. Profiles are preference bundles chosen by the
pupil, a parent or a teacher: they are never diagnoses and never inferred.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional, Union
from xml.sax.saxutils import escape as _xml_escape

__all__ = [
    "Profile", "PROFILES", "NEEDS", "Finding", "AdaptedReply", "fr_number", "en_number",
    "number_to_words", "spoken_math", "to_mathml", "lint", "adapt", "profile_prompt_addendum",
    "explain_profile", "combine_profiles", "get_profile",
]

# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

#: Vocabulary of needs (presentation needs, not conditions).
NEEDS: dict[str, tuple[str, str]] = {
    "lecture_ecran": ("lecture par lecteur d'écran ou plage braille", "reading through a screen reader or braille display"),
    "acces_audio": ("sortie vocale (synthèse) des réponses", "speech output of the replies"),
    "vision_reduite": ("vision réduite, besoin de contraste", "reduced vision, need for contrast"),
    "agrandissement": ("agrandissement de l'affichage (zoom)", "enlarged display (zoom)"),
    "lecture_fluente": ("lecture facilitée, texte aéré", "easier reading, airy text"),
    "nombres_symboles": ("nombres et symboles lus clairement", "numbers and symbols read clearly"),
    "charge_cognitive": ("peu d'informations à la fois", "little information at a time"),
    "attention_soutenue": ("aide pour garder l'attention, une chose à la fois", "help to stay focused, one thing at a time"),
    "langage_litteral": ("langage littéral, sans image ni sous-entendu", "literal language, no figures of speech or implicit meaning"),
    "previsibilite": ("structure prévisible d'un message à l'autre", "predictable structure from one message to the next"),
    "rythme_personnel": ("avancer à son rythme, sans pression de temps", "working at one's own pace, no time pressure"),
    "texte_prioritaire": ("information écrite d'abord, jamais un son seul", "written information first, never sound alone"),
    "motricite_fine": ("peu de saisie au clavier, réponses courtes", "little typing, short answers"),
}


@dataclass(frozen=True)
class Profile:
    """A named bundle of presentation preferences (never a diagnosis)."""
    name: str
    label_fr: str
    label_en: str
    needs: tuple[str, ...]
    max_sentence_words: Optional[int]
    max_steps_per_reply: Optional[int]
    forbid_figurative: bool
    forbid_time_pressure: bool
    spoken_math: bool
    limit_symbols: bool
    limit_emoji: Optional[int]


def _p(name, fr, en, needs, msw, steps, fig, tp, spoken, sym, emoji) -> Profile:
    return Profile(name, fr, en, tuple(needs), msw, steps, fig, tp, spoken, sym, emoji)


PROFILES: dict[str, Profile] = {p.name: p for p in (
    _p("default", "Standard (aucune adaptation)", "Standard (no adaptation)", (), None, None, False, False, False, False, None),
    _p("lecture_vocale", "Lecture vocale / lecteur d'écran", "Speech output / screen reader",
       ("lecture_ecran", "acces_audio"), 20, 3, False, False, True, True, 0),
    _p("contraste_zoom", "Contraste et zoom", "Contrast and zoom",
       ("vision_reduite", "agrandissement"), 18, 3, False, False, False, True, 1),
    _p("texte_aere", "Texte aéré (lecture facilitée)", "Airy text (easier reading)",
       ("lecture_fluente",), 14, 3, False, False, False, False, 2),
    _p("nombres_clairs", "Nombres et symboles clairs", "Clear numbers and symbols",
       ("nombres_symboles", "charge_cognitive"), 15, 2, False, False, True, True, 1),
    _p("une_etape_a_la_fois", "Une étape à la fois", "One step at a time",
       ("attention_soutenue", "charge_cognitive"), 12, 1, False, True, False, False, 1),
    _p("langage_litteral", "Langage littéral, structure prévisible", "Literal language, predictable structure",
       ("langage_litteral", "previsibilite"), 15, 3, True, True, False, False, 0),
    _p("sans_pression_temps", "Sans pression de temps", "No time pressure",
       ("rythme_personnel", "previsibilite"), None, 3, False, True, False, False, None),
    _p("texte_prioritaire", "Texte d'abord (jamais un son seul)", "Text first (never sound alone)",
       ("texte_prioritaire",), 18, 3, False, False, False, False, 2),
    _p("reponses_courtes", "Réponses courtes (peu de saisie)", "Short answers (little typing)",
       ("motricite_fine",), 18, 2, False, False, False, False, 2),
)}


def get_profile(profile: Union[Profile, str]) -> Profile:
    """Resolve a profile object or name."""
    if isinstance(profile, Profile):
        return profile
    try:
        return PROFILES[profile]
    except KeyError:
        raise ValueError(f"unknown profile {profile!r}; known: {', '.join(PROFILES)}") from None


def combine_profiles(names: list[str], name: Optional[str] = None) -> Profile:
    """Merge several profiles: strictest limit wins, booleans are OR-ed."""
    ps = [get_profile(n) for n in names]
    if not ps:
        return PROFILES["default"]

    def low(vals: list) -> Optional[int]:
        vals = [v for v in vals if v is not None]
        return min(vals) if vals else None

    needs: list[str] = []
    for p in ps:
        needs.extend(n for n in p.needs if n not in needs)
    return Profile(
        name or "+".join(p.name for p in ps),
        " + ".join(p.label_fr for p in ps), " + ".join(p.label_en for p in ps), tuple(needs),
        low([p.max_sentence_words for p in ps]), low([p.max_steps_per_reply for p in ps]),
        any(p.forbid_figurative for p in ps), any(p.forbid_time_pressure for p in ps),
        any(p.spoken_math for p in ps), any(p.limit_symbols for p in ps),
        low([p.limit_emoji for p in ps]),
    )


# ---------------------------------------------------------------------------
# Number to words
# ---------------------------------------------------------------------------

_FR_UNITS = ["zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix",
             "onze", "douze", "treize", "quatorze", "quinze", "seize"]
_FR_TENS = {2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante", 6: "soixante"}


def _fr_lt20(n: int) -> str:
    return _FR_UNITS[n] if n < 17 else "dix-" + _FR_UNITS[n - 10]


def _fr_lt100(n: int, final: bool) -> str:
    if n < 20:
        return _fr_lt20(n)
    if n < 70:
        t, u = divmod(n, 10)
        if u == 0:
            return _FR_TENS[t]
        if u == 1:
            return _FR_TENS[t] + " et un"
        return _FR_TENS[t] + "-" + _FR_UNITS[u]
    if n < 80:
        r = n - 60
        return "soixante et onze" if r == 11 else "soixante-" + _fr_lt20(r)
    r = n - 80
    if r == 0:
        return "quatre-vingts" if final else "quatre-vingt"
    return "quatre-vingt-" + _fr_lt20(r)


def _fr_lt1000(n: int, final: bool) -> str:
    h, r = divmod(n, 100)
    if h == 0:
        return _fr_lt100(r, final)
    head = "cent" if h == 1 else _FR_UNITS[h] + " cent" + ("s" if r == 0 and final else "")
    return head if r == 0 else head + " " + _fr_lt100(r, final)


def fr_number(n: int) -> str:
    """French cardinal in words (|n| < 10**9), 1990-style hyphens, 'et un' rules."""
    if n < 0:
        return "moins " + fr_number(-n)
    if n == 0:
        return "zéro"
    if n >= 10 ** 9:
        raise ValueError("number too large")
    parts = []
    mil, rest = divmod(n, 10 ** 6)
    if mil:
        parts.append(_fr_lt1000(mil, True) + (" million" if mil == 1 else " millions"))
    th, r = divmod(rest, 1000)
    if th:
        parts.append("mille" if th == 1 else _fr_lt1000(th, False) + " mille")
    if r:
        parts.append(_fr_lt1000(r, True))
    return " ".join(parts)


_EN_UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
             "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
             "eighteen", "nineteen"]
_EN_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def _en_lt100(n: int) -> str:
    if n < 20:
        return _EN_UNITS[n]
    t, u = divmod(n, 10)
    return _EN_TENS[t] + ("-" + _EN_UNITS[u] if u else "")


def _en_lt1000(n: int) -> str:
    h, r = divmod(n, 100)
    if h == 0:
        return _en_lt100(r)
    return _EN_UNITS[h] + " hundred" + (" " + _en_lt100(r) if r else "")


def en_number(n: int) -> str:
    """English cardinal in words (|n| < 10**9), no 'and'."""
    if n < 0:
        return "minus " + en_number(-n)
    if n == 0:
        return "zero"
    if n >= 10 ** 9:
        raise ValueError("number too large")
    parts = []
    for size, label in ((10 ** 6, " million"), (1000, " thousand")):
        q, n = divmod(n, size)
        if q:
            parts.append(_en_lt1000(q) + label)
    if n:
        parts.append(_en_lt1000(n))
    return " ".join(parts)


def number_to_words(n: int, lang: str = "fr") -> str:
    """Integer to words in French or English."""
    return fr_number(n) if _lang(lang) == "fr" else en_number(n)


def _lang(lang: str) -> str:
    lang = (lang or "fr").lower()[:2]
    if lang not in ("fr", "en"):
        raise ValueError(f"unsupported language {lang!r} (fr or en)")
    return lang


def _fr_ordinal(n: int, fem: bool = False) -> str:
    if n == 1:
        return "première" if fem else "premier"
    w = fr_number(n)
    if w.endswith("cinq"):
        w += "u"
    elif w.endswith("neuf"):
        w = w[:-1] + "v"
    elif w.endswith("e"):
        w = w[:-1]
    elif w.endswith(("vingts", "cents", "millions")):
        w = w[:-1]
    return w + "ième"


def _en_ordinal(n: int) -> str:
    w = en_number(n)
    cut = max(w.rfind(" "), w.rfind("-")) + 1
    head, last = w[:cut], w[cut:]
    irregular = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
                 "nine": "ninth", "twelve": "twelfth"}
    if last in irregular:
        last = irregular[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last += "th"
    return head + last


def _en_year(y: int) -> str:
    if 1100 <= y <= 2099 and not 2000 <= y <= 2009:
        hi, lo = divmod(y, 100)
        if lo == 0:
            return en_number(hi) + " hundred"
        return en_number(hi) + " " + (("oh " + en_number(lo)) if lo < 10 else en_number(lo))
    return en_number(y)


def _digits_words(ds: str, lang: str) -> str:
    return " ".join((_FR_UNITS[int(d)] if lang == "fr" else _EN_UNITS[int(d)]) for d in ds)


def _num_words(numstr: str, lang: str, fem: bool = False) -> str:
    norm = re.sub(r"[ \u00a0\u202f]", "", numstr).replace(",", ".")
    ip, _, fp = norm.partition(".")
    has_frac = "." in norm
    if len(ip) > 9:
        iw = _digits_words(ip, lang)
    else:
        iw = number_to_words(int(ip), lang)
        if fem and lang == "fr" and not has_frac and iw.endswith("un"):
            iw += "e"
    if not has_frac:
        return iw
    if lang == "fr":
        fw = _digits_words(fp, lang) if (fp.startswith("0") or len(fp) > 3) else fr_number(int(fp))
        return f"{iw} virgule {fw}"
    return f"{iw} point {_digits_words(fp, lang)}"


def _is_plural(numstr: str, lang: str) -> bool:
    v = Decimal(re.sub(r"[ \u00a0\u202f]", "", numstr).replace(",", "."))
    return abs(v) >= 2 if lang == "fr" else v != 1


# ---------------------------------------------------------------------------
# Spoken math
# ---------------------------------------------------------------------------

_W = {
    "fr": dict(plus="plus", minus="moins", times="fois", div="divisé par", eq="égale", ne="différent de",
               le="inférieur ou égal à", ge="supérieur ou égal à", lt="inférieur à", gt="supérieur à",
               approx="environ égal à", over="sur", sq="au carré", cube="au cube", pow="puissance",
               sqrt="racine carrée de", cbrt="racine cubique de", endroot="fin de racine", pi="pi",
               percent="pour cent", permille="pour mille", inf="l'infini", pm="plus ou moins",
               isin="appartient à", union="union", inter="intersection", angle="angle",
               perp="perpendiculaire à", par="parallèle à", gives="donne", implies="implique",
               iff="équivaut à", therefore="donc", because="car", lp="parenthèse ouverte",
               rp="parenthèse fermée", sub="indice", vec="vecteur", seg="segment", semi="point-virgule",
               fracc="la fraction de numérateur {a} et de dénominateur {b}", slash="barre oblique",
               of="de", deg="degrés", rootn="racine d'indice {n} de"),
    "en": dict(plus="plus", minus="minus", times="times", div="divided by", eq="equals", ne="not equal to",
               le="less than or equal to", ge="greater than or equal to", lt="less than", gt="greater than",
               approx="approximately equal to", over="over", sq="squared", cube="cubed",
               pow="to the power of", sqrt="square root of", cbrt="cube root of", endroot="end of root",
               pi="pi", percent="percent", permille="per mille", inf="infinity", pm="plus or minus",
               isin="belongs to", union="union", inter="intersection", angle="angle",
               perp="perpendicular to", par="parallel to", gives="gives", implies="implies",
               iff="is equivalent to", therefore="therefore", because="because", lp="open parenthesis",
               rp="close parenthesis", sub="sub", vec="vector", seg="segment", semi="semicolon",
               fracc="the fraction with numerator {a} and denominator {b}", slash="slash",
               of="of", deg="degrees", rootn="root of index {n} of"),
}

_GREEK = {
    "π": ("pi", "pi"), "α": ("alpha", "alpha"), "β": ("bêta", "beta"), "γ": ("gamma", "gamma"),
    "δ": ("delta", "delta"), "Δ": ("delta", "delta"), "θ": ("thêta", "theta"), "λ": ("lambda", "lambda"),
    "μ": ("mu", "mu"), "σ": ("sigma", "sigma"), "φ": ("phi", "phi"), "ω": ("oméga", "omega"),
    "ε": ("epsilon", "epsilon"),
}

_LATEX_SYMS = {
    "times": "×", "cdot": "·", "div": "÷", "leq": "≤", "le": "≤", "leqslant": "≤", "geq": "≥", "ge": "≥",
    "geqslant": "≥", "neq": "≠", "ne": "≠", "approx": "≈", "pi": "π", "pm": "±", "infty": "∞",
    "to": "→", "rightarrow": "→", "Rightarrow": "⇒", "Leftrightarrow": "⇔", "in": "∈", "cup": "∪",
    "cap": "∩", "angle": "∠", "perp": "⟂", "parallel": "∥", "alpha": "α", "beta": "β", "gamma": "γ",
    "delta": "δ", "Delta": "Δ", "theta": "θ", "lambda": "λ", "mu": "μ", "sigma": "σ", "phi": "φ",
    "omega": "ω", "epsilon": "ε", "ldots": "…", "dots": "…", "cdots": "…", "therefore": "∴",
}
_TEXT_CMDS = {"text", "mathrm", "mathbf", "textbf", "mbox", "operatorname", "mathit", "textit", "textrm"}
_SPACE_CMDS = {"quad", "qquad", "displaystyle", "hspace", "hfill", "limits", "nolimits", "textstyle"}

# unit key -> (fr singular, fr plural, en singular, en plural, feminine in French)
_UNITS: dict[str, tuple[str, str, str, str, bool]] = {}


def _u(keys: str, fs: str, fp: str, es: str, ep: str, fem: bool = False) -> None:
    for k in keys.split():
        _UNITS[k] = (fs, fp, es, ep, fem)


_u("mm", "millimètre", "millimètres", "millimeter", "millimeters")
_u("cm", "centimètre", "centimètres", "centimeter", "centimeters")
_u("dm", "décimètre", "décimètres", "decimeter", "decimeters")
_u("m", "mètre", "mètres", "meter", "meters")
_u("km", "kilomètre", "kilomètres", "kilometer", "kilometers")
_u("mg", "milligramme", "milligrammes", "milligram", "milligrams")
_u("g", "gramme", "grammes", "gram", "grams")
_u("kg", "kilogramme", "kilogrammes", "kilogram", "kilograms")
_u("t", "tonne", "tonnes", "tonne", "tonnes", True)
_u("mL ml", "millilitre", "millilitres", "milliliter", "milliliters")
_u("cL cl", "centilitre", "centilitres", "centiliter", "centiliters")
_u("dL dl", "décilitre", "décilitres", "deciliter", "deciliters")
_u("L l", "litre", "litres", "liter", "liters")
_u("s", "seconde", "secondes", "second", "seconds", True)
_u("min", "minute", "minutes", "minute", "minutes", True)
_u("h", "heure", "heures", "hour", "hours", True)
_u("ha", "hectare", "hectares", "hectare", "hectares")
_u("km/h", "kilomètre par heure", "kilomètres par heure", "kilometer per hour", "kilometers per hour")
_u("m/s", "mètre par seconde", "mètres par seconde", "meter per second", "meters per second")
_SYMBOL_UNITS = {
    "%": ("pour cent", "pour cent", "percent", "percent"),
    "‰": ("pour mille", "pour mille", "per mille", "per mille"),
    "€": ("euro", "euros", "euro", "euros"),
    "°C": ("degré Celsius", "degrés Celsius", "degree Celsius", "degrees Celsius"),
    "°F": ("degré Fahrenheit", "degrés Fahrenheit", "degree Fahrenheit", "degrees Fahrenheit"),
    "°": ("degré", "degrés", "degree", "degrees"),
}
_MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
              "octobre", "novembre", "décembre"]
_MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
              "October", "November", "December"]
_ACRONYMS = {"TVA", "PGCD", "PPCM", "SOH", "CAH", "TOA", "QCM", "CNIL", "RGPD", "SVT", "EPS", "PDF", "HTML",
             "OCDE", "DNB", "USA", "ONU", "CDI", "CPE"}
_GEO_CONTEXT = {"segment", "droite", "demi-droite", "angle", "triangle", "côté", "côtés", "point", "points",
                "vecteur", "arc", "cercle", "longueur", "distance", "mesure", "line", "ray", "side",
                "vector", "length", "sides", "quadrilatère", "rectangle", "carré", "parallélogramme",
                "losange", "trapèze", "square", "quadrilateral"}

_NUM = r"(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?!\d)(?:[,.]\d+)?|\d+(?:[,.]\d+)?)"
_UNIT_ALT = "|".join(sorted((re.escape(k) for k in _UNITS), key=len, reverse=True))
_NUM_UNIT_RE = re.compile(
    rf"(?<![\d,.])(?P<num>{_NUM})(?P<sp>[ \u00a0\u202f]?)"
    rf"(?:(?P<u>{_UNIT_ALT})(?P<pow>[²³])?(?![\w'’/²³])|(?P<sym>°C|°F|°|%|‰|€)(?!\w))")
_BARE_COMPOUND_RE = re.compile(r"(?<![\w/])(?P<u>km/h|m/s)(?![\w/])")
_EN_UNIT_RE = re.compile(rf"\b(?P<w>en|in)\s+(?P<u>{_UNIT_ALT})(?P<pow>[²³])?(?![\w'’/²³])")
_NUMBER_RE = re.compile(rf"(?<![\d,.]){_NUM}")
_SUP_MAP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
_SUP_RE = re.compile("[⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+")
_LOP, _ROP = "\ue000", "\ue001"
_FRAC_NAT = {"fr": {(1, 2): "un demi", (1, 3): "un tiers", (2, 3): "deux tiers", (1, 4): "un quart", (3, 4): "trois quarts"},
             "en": {(1, 2): "one half", (1, 3): "one third", (2, 3): "two thirds", (1, 4): "one quarter", (3, 4): "three quarters"}}
_SIMPLE_ARG = re.compile(r"^\s*-?\s*(?:\d+(?:[,.]\d+)?|[A-Za-z]|π)\s*$")


def _strip_markup(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("```", "").replace("`", "")
    s = re.sub(r"(?m)^[ \t]*#{1,6}[ \t]+", "", s)
    s = re.sub(r"(?m)^[ \t]*>[ \t]?", "", s)
    s = re.sub(r"(?m)^[ \t]*[-*•][ \t]+", "", s)
    s = re.sub(r"(\*\*|__)(.+?)\1", r"\2", s, flags=re.S)
    s = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"\1", s)
    s = re.sub(r"(?<![\w])_([^_\s][^_]*?)_(?![\w])", r"\1", s)
    return s


def _is_mathy(inner: str) -> bool:
    if "\\" in inner:
        return True
    if re.search(r"[A-Za-zÀ-ÿ]{4,}", inner):
        return False
    return bool(re.search(r"[=+×÷*<>≤≥≠≈√π^/−;²³·]|\s-\s|\d-\d|^\s*-|\(\s*-", inner))


def _mark_parens(s: str) -> str:
    stack: list[int] = []
    pairs: dict[int, int] = {}
    for i, ch in enumerate(s):
        if ch == "(":
            stack.append(i)
        elif ch == ")" and stack:
            pairs[stack.pop()] = i
    chars = list(s)
    for a, b in pairs.items():
        if _is_mathy(s[a + 1:b]):
            chars[a], chars[b] = _LOP, _ROP
    return "".join(chars)


def _read_group(s: str, i: int) -> tuple[str, int]:
    depth = 0
    j = i
    while j < len(s):
        if s[j] == "\\":
            j += 2
            continue
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], len(s)


def _arg(s: str, j: int) -> tuple[str, int]:
    if j < len(s) and s[j] == "{":
        return _read_group(s, j)
    if j < len(s) and s[j] == "\\":
        m = re.compile(r"\\[A-Za-z]+").match(s, j)
        if m:
            return m.group(0), m.end()
    return (s[j], j + 1) if j < len(s) else ("", j)


_CMD_RE = re.compile(r"\\([A-Za-z]+)")
_EXP_RE = re.compile(r"[-−+]?\d+|[A-Za-z]|π")


def _structural(s: str, lang: str, style: str) -> str:
    """Resolve LaTeX commands, braces, ^ and _ into words / unicode marks."""
    W = _W[lang]
    out: list[str] = []
    i, n = 0, len(s)

    def sk(j: int) -> int:
        while j < n and s[j] in " \t\n":
            j += 1
        return j

    def sp(x: str) -> str:
        return spoken_math(x, lang, style)

    while i < n:
        ch = s[i]
        if ch == "\\":
            m = _CMD_RE.match(s, i)
            if not m:
                nxt = s[i + 1] if i + 1 < n else ""
                out.append(nxt if nxt in "%$&#_{}" else " ")
                i += 2
                continue
            cmd, i = m.group(1), m.end()
            if cmd in ("frac", "dfrac", "tfrac"):
                a, j = _arg(s, sk(i))
                b, j = _arg(s, sk(j))
                i = j
                out.append(" " + _frac_words(a, b, lang, style) + " ")
            elif cmd == "sqrt":
                idx = None
                if i < n and s[i] == "[":
                    k = s.find("]", i)
                    k = n - 1 if k < 0 else k
                    idx, i = s[i + 1:k], k + 1
                a, i = _arg(s, sk(i))
                inner = sp(a)
                if idx is None or idx.strip() == "2":
                    head = W["sqrt"]
                elif idx.strip() == "3":
                    head = W["cbrt"]
                else:
                    head = W["rootn"].format(n=sp(idx))
                tail = "" if _SIMPLE_ARG.match(a) else ", " + W["endroot"]
                out.append(f" {head} {inner}{tail} ")
            elif cmd in _TEXT_CMDS:
                a, i = _arg(s, sk(i))
                out.append(_structural(a, lang, style))
            elif cmd in ("left", "right"):
                if i < n and s[i] == ".":
                    i += 1
            elif cmd in ("widehat", "hat"):
                a, i = _arg(s, sk(i))
                out.append(" ∠" + _structural(a, lang, style) + " ")
            elif cmd in ("vec", "overrightarrow"):
                a, i = _arg(s, sk(i))
                out.append(f" {W['vec']} " + _structural(a, lang, style) + " ")
            elif cmd == "overline":
                a, i = _arg(s, sk(i))
                out.append(f" {W['seg']} " + _structural(a, lang, style) + " ")
            elif cmd in ("begin", "end"):
                _, i = _arg(s, sk(i))
            elif cmd in ("circ", "degree"):
                out.append("°")
            elif cmd in _LATEX_SYMS:
                out.append(" " + _LATEX_SYMS[cmd] + " ")
            elif cmd in _SPACE_CMDS:
                out.append(" ")
            else:
                out.append(" " + cmd + " ")
        elif ch == "$":
            i += 1
        elif ch in "{}":
            i += 1
        elif ch == "^":
            i += 1
            if i < n and s[i] == "{":
                e, i = _read_group(s, i)
            elif i < n and s[i] == "\\":
                m = _CMD_RE.match(s, i)
                e, i = ("\\" + m.group(1), m.end()) if m else ("", i + 1)
            elif i < n and s[i] in "(" + _LOP:
                close = _ROP if s[i] == _LOP else ")"
                k = s.find(close, i)
                k = n if k < 0 else k
                e, i = s[i + 1:k], k + 1
            else:
                m = _EXP_RE.match(s, i)
                e, i = (m.group(0), m.end()) if m else ("", i)
            e = e.strip()
            tail = "".join(out)[-6:]
            if e in ("\\circ", "\\degree"):
                out.append("°")
            elif e in ("2", "3") and not re.search(r"(?<![\d,.])10$", tail):
                out.append("²" if e == "2" else "³")
            elif e:
                out.append(f" {W['pow']} {sp(e)} ")
        elif ch == "_" and out and i + 1 < n and (out[-1][-1:].isalnum() or out[-1][-1:] == "}"):
            i += 1
            if s[i] == "{":
                e, i = _read_group(s, i)
            else:
                m = re.compile(r"\d+|[A-Za-z]").match(s, i)
                e, i = (m.group(0), m.end()) if m else ("", i)
            out.append(f" {W['sub']} {sp(e)} " if e else "")
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _frac_words(a: str, b: str, lang: str, style: str) -> str:
    W = _W[lang]
    A, B = spoken_math(a, lang, style), spoken_math(b, lang, style)
    if _SIMPLE_ARG.match(a) and _SIMPLE_ARG.match(b):
        if style == "natural":
            try:
                key = (int(a), int(b))
            except ValueError:
                key = None
            if key in _FRAC_NAT[lang]:
                return _FRAC_NAT[lang][key]
        return f"{A} {W['over']} {B}"
    return W["fracc"].format(a=A, b=B)


def _unit_words(key: str, pow_: Optional[str], plural: bool, lang: str) -> str:
    if key in _UNITS:
        fs, fp, es, ep, _ = _UNITS[key]
    else:
        fs, fp, es, ep = _SYMBOL_UNITS[key]
    if lang == "fr":
        w = fp if plural else fs
        if pow_:
            w += " " + ("carré" if pow_ == "²" else "cube") + ("s" if plural else "")
        return w
    w = ep if plural else es
    return (("square " if pow_ == "²" else "cubic ") + w) if pow_ else w


def _ordinal_sub(s: str, lang: str) -> str:
    if lang == "fr":
        def rep(m: re.Match) -> str:
            n = int(m.group(1))
            if n == 0 or n > 999999:
                return m.group(0)
            return " " + _fr_ordinal(n, fem=m.group(2) in ("re", "ère")) + " "
        return re.sub(r"(?<![\d,.])(\d+)(er|ère|re|ème|e|è)(?!\w)", rep, s)

    def rep_en(m: re.Match) -> str:
        n = int(m.group(1))
        return m.group(0) if n == 0 or n > 999999 else " " + _en_ordinal(n) + " "
    return re.sub(r"(?<![\d,.])(\d+)(st|nd|rd|th)(?!\w)", rep_en, s)


def _dates(s: str, lang: str) -> str:
    def words_date(d: int, mth: int, y: int) -> str:
        if lang == "fr":
            day = "premier" if d == 1 else fr_number(d)
            return f" {day} {_MONTHS_FR[mth - 1]} {fr_number(y)} "
        return f" {_MONTHS_EN[mth - 1]} {_en_ordinal(d)}, {_en_year(y)} "

    def iso(m: re.Match) -> str:
        y, mth, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return words_date(d, mth, y) if 1 <= mth <= 12 and 1 <= d <= 31 else m.group(0)

    def dmy(m: re.Match) -> str:
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if lang == "fr" and 1 <= mth <= 12 and 1 <= d <= 31:
            return words_date(d, mth, y)
        w = _W[lang]["slash"]
        return f" {m.group(1)} {w} {m.group(2)} {w} {m.group(3)} "

    s = re.sub(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])", iso, s)
    return re.sub(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{2,4})(?![\d/])", dmy, s)


def _units_stage(s: str, lang: str) -> str:
    def clock(m: re.Match) -> str:
        h, mi = int(m.group(1)), int(m.group(2))
        if h > 24 or mi > 59:
            return m.group(0)
        hw = _num_words(m.group(1), lang, fem=True)
        mw = _num_words(m.group(2), lang)
        if lang == "fr":
            return f" {hw} heure{'s' if h >= 2 else ''} {mw} "
        return f" {hw} hour{'s' if h != 1 else ''} {mw} "

    s = re.sub(r"(?<![\d,.])(\d{1,2})\s?h\s?(\d{2})(?![\d\w])", clock, s)

    def repl(m: re.Match) -> str:
        key = m.group("u") or m.group("sym")
        if m.group("u") and len(key) == 1 and not m.group("sp"):
            rest = m.string[m.end():]
            if not (key == "h" and not m.group("pow") and re.match(r"\s*(?:$|[.,;:!?)\]]|[a-zà-ÿ]{2,})", rest, re.I)):
                return m.group(0)
        fem = bool(m.group("u")) and _UNITS[key][4] and lang == "fr"
        nw = _num_words(m.group("num"), lang, fem=fem)
        return f" {nw} {_unit_words(key, m.group('pow'), _is_plural(m.group('num'), lang), lang)} "

    s = _NUM_UNIT_RE.sub(repl, s)
    s = _BARE_COMPOUND_RE.sub(lambda m: " " + _unit_words(m.group("u"), None, True, lang) + " ", s)
    return _EN_UNIT_RE.sub(lambda m: f" {m.group('w')} " + _unit_words(m.group("u"), m.group("pow"), True, lang) + " ", s)


def _symbols_stage(s: str, lang: str, style: str) -> str:
    W = _W[lang]
    sp = lambda k: f" {W[k]} "  # noqa: E731

    def sup(m: re.Match) -> str:
        t = m.group(0)
        if t == "²":
            return sp("sq")
        if t == "³":
            return sp("cube")
        return f" {W['pow']} {spoken_math(t.translate(_SUP_MAP), lang, style)} "

    s = _SUP_RE.sub(sup, s)
    # chains of ASCII operators first
    for pat, ch in (("<=>", "⇔"), ("=>", "⇒"), ("->", "→"), ("<=", "≤"), (">=", "≥"), ("!=", "≠"), ("~=", "≈")):
        s = s.replace(pat, ch)
    # fractions a/b with simple operands
    def frac(m: re.Match) -> str:
        a, b = m.group(1), m.group(2)
        if style == "natural" and a.isdigit() and b.isdigit() and (int(a), int(b)) in _FRAC_NAT[lang]:
            return " " + _FRAC_NAT[lang][(int(a), int(b))] + " "
        return f" {a} {W['over']} {b} "
    s = re.sub(r"(?<![\w/.,])(\d+(?:[,.]\d+)?|[A-Za-z])\s?/\s?(\d+(?:[,.]\d+)?|[A-Za-z])(?![\w/])", frac, s)
    s = re.sub(rf"(?<=[\d)²³{_ROP}])\s?/\s?(?=[\d(√π{_LOP}]|[A-Za-z](?![A-Za-z]))", sp("over"), s)
    s = re.sub(rf"(?<![A-Za-z])(?<=[A-Za-z])\s?/\s?(?=[\d(√π{_LOP}])", sp("over"), s)
    s = re.sub(r"(?<=[\d)])[ \u00a0]?;[ \u00a0]?(?=[-−\d(])", sp("semi"), s)
    s = re.sub(r"(?<![A-Za-z])(?<=[A-Za-z])[ \u00a0]?;[ \u00a0]?(?=[A-Za-z](?![A-Za-z]))", sp("semi"), s)
    # minus signs
    s = s.replace("−", sp("minus"))
    s = re.sub(rf"(?:^|(?<=[\s=+×÷*<>≤≥≠≈(;/{_LOP}]))-(?=[\d√π{_LOP}]|[A-Za-z](?![A-Za-z]))", sp("minus"), s, flags=re.M)
    s = re.sub(rf"(?<=[\d)²³{_ROP}])-(?=[\d(√π{_LOP}]|[A-Za-z](?![A-Za-z]))", sp("minus"), s)
    s = re.sub(rf"(?P<a>[\d)²³{_ROP}]|(?<![^\W\d_])[^\W\d_])[ \u00a0]-[ \u00a0](?=[\d(√π{_LOP}]|[^\W\d_](?![^\W\d_]))",
               lambda m: m.group("a") + sp("minus"), s)
    # multiplication
    s = re.sub(rf"(?<=[\d)²³{_ROP}])\s?\*\s?(?=[\d({_LOP}√π])|(?<=\w) \* (?=\w)|(?<=[A-Za-z])\*(?=[A-Za-z])", sp("times"), s)
    s = re.sub(rf"(?<=[\w)²³{_ROP}])\s?·\s?(?=[\w({_LOP}])", sp("times"), s)
    table = {"+": "plus", "×": "times", "÷": "div", "=": "eq", "≠": "ne", "≤": "le", "≥": "ge", "<": "lt", ">": "gt",
             "≈": "approx", "√": "sqrt", "∞": "inf", "±": "pm", "∈": "isin", "∪": "union", "∩": "inter",
             "∠": "angle", "⟂": "perp", "∥": "par", "→": "gives", "⇒": "implies", "⇔": "iff", "∴": "therefore",
             "∵": "because", _LOP: "lp", _ROP: "rp"}
    for ch, key in table.items():
        if key is None:
            continue
        elif ch in s:
            s = s.replace(ch, sp(key))
    for ch, (fr, en) in _GREEK.items():
        s = s.replace(ch, f" {fr if lang == 'fr' else en} ")
    s = s.replace("%", sp("percent")).replace("‰", sp("permille")).replace("°", sp("deg")).replace("€", " euros " if lang == "fr" else " euros ")
    return s


def _number_stage(s: str, lang: str) -> str:
    def rep(m: re.Match) -> str:
        before = s[m.start() - 1] if m.start() else ""
        after = s[m.end()] if m.end() < len(s) else ""
        lead = " " if (before.isalnum() or before == ")" or before.isspace() or before == "") else ""
        tail = " " if (after.isalnum() or after.isspace() or after == "") else ""
        return lead + _num_words(m.group(0), lang) + tail
    return _NUMBER_RE.sub(rep, s)


def _geometry_spacing(s: str, lang: str) -> str:
    W = _W[lang]
    follow = {W[k] for k in ("eq", "ne", "le", "ge", "lt", "gt", "approx")}

    def rep(m: re.Match) -> str:
        tok = m.group(0)
        if tok in _ACRONYMS:
            return tok
        before = s[:m.start()].rstrip(" [(").split()
        prev = before[-1].lower().strip(",.;:") if before else ""
        after = s[m.end():].lstrip(" ])").split()
        nxt = after[0] if after else ""
        adjacent = s[max(0, m.start() - 1):m.start()] in "[(" and s[m.end():m.end() + 1] in "])"
        if prev in _GEO_CONTEXT or nxt in follow or adjacent or (len(tok) <= 3 and nxt in (W["sq"], W["cube"])):
            return " ".join(tok)
        return tok
    return re.sub(r"(?<![\w])[A-Z]{2,4}(?![\w])", rep, s)


def spoken_math(text: str, lang: str = "fr", style: str = "explicit") -> str:
    """Convert math inside plain/unicode/simple-LaTeX text to speakable words.

    style='explicit' reads fractions as 'trois sur quatre' (unambiguous);
    style='natural' uses 'trois quarts' only for halves, thirds and quarters.
    """
    lang = _lang(lang)
    if style not in ("explicit", "natural"):
        raise ValueError("style must be 'explicit' or 'natural'")
    s = _strip_markup(text)
    s = s.replace("\u2009", " ")
    s = re.sub(r"\bsqrt\s*\(", "√(", s)
    s = re.sub(r"\b([fgh])\(([^()]*)\)",
               lambda m: f"{m.group(1)} {_W[lang]['of']} " + (f"({m.group(2)})" if _is_mathy(m.group(2)) else m.group(2)), s)
    s = _mark_parens(s)
    s = _structural(s, lang, style)
    s = _dates(s, lang)
    s = _ordinal_sub(s, lang)
    s = _units_stage(s, lang)
    s = _symbols_stage(s, lang, style)
    s = _number_stage(s, lang)
    s = _geometry_spacing(s, lang)
    s = re.sub(r"[ \t\u00a0]+", " ", s)
    s = re.sub(r" +([,.;])", r"\1", s)
    s = re.sub(r"(?m)^ +| +$", "", s)
    return s.strip()


# ---------------------------------------------------------------------------
# MathML
# ---------------------------------------------------------------------------

_MML_FUNCS = {"sin", "cos", "tan", "ln", "log", "exp", "max", "min"}
_MML_UNITS = {"mm", "cm", "dm", "m", "km", "mg", "g", "kg", "t", "mL", "cL", "dL", "L", "ml", "cl", "dl", "l",
              "s", "min", "h", "ha"}
_MML_OPS = {"+": "+", "-": "−", "−": "−", "×": "×", "÷": "÷", "*": "×", "·": "×", "=": "=", "<": "<", ">": ">",
            "≤": "≤", "≥": "≥", "≠": "≠", "≈": "≈", "±": "±"}
_MML_CMD_OPS = {"times": "×", "cdot": "×", "div": "÷", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥",
                "neq": "≠", "ne": "≠", "approx": "≈", "pm": "±"}
_MML_NUM = re.compile(r"\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?!\d)(?:[,.]\d+)?|\d+(?:[,.]\d+)?")
_MML_SIMPLE_FRAC = re.compile(r"\s?/\s?(\d+(?:[,.]\d+)?|[A-Za-z](?![A-Za-z]))(?![\^_²³\d(])")


class _MathMLParser:
    def __init__(self, s: str) -> None:
        self.s = s
        self.i = 0
        self.depth = 0

    def err(self, msg: str) -> ValueError:
        return ValueError(f"unsupported math at position {self.i}: {msg}")

    def ws(self) -> None:
        while self.i < len(self.s) and self.s[self.i] in " \t\n":
            self.i += 1

    def peek(self) -> str:
        return self.s[self.i] if self.i < len(self.s) else ""

    def seq(self, closers: str) -> list[str]:
        self.depth += 1
        if self.depth > 30:
            raise self.err("nesting too deep")
        out: list[str] = []
        prev_operand = False
        prev_num = False
        while True:
            self.ws()
            c = self.peek()
            if c == "" or c in closers:
                break
            if c == "\\":
                m = _CMD_RE.match(self.s, self.i)
                if m and m.group(1) in _MML_CMD_OPS:
                    self.i = m.end()
                    out.append(f"<mo>{_MML_CMD_OPS[m.group(1)]}</mo>")
                    prev_operand = prev_num = False
                    continue
                if m and m.group(1) in ("left", "right"):
                    self.i = m.end()
                    continue
            if c in _MML_OPS:
                self.i += 1
                out.append(f"<mo>{_xml_escape(_MML_OPS[c])}</mo>")
                prev_operand = prev_num = False
                continue
            if c == "/":
                self.i += 1
                out.append("<mo>/</mo>")
                prev_operand = prev_num = False
                continue
            atoms, is_num = self.postfix()
            if prev_operand:
                if prev_num and is_num:
                    raise self.err("two adjacent numbers")
                out.append("<mo>&#x2062;</mo>")
            out.extend(atoms)
            prev_operand, prev_num = True, is_num
        self.depth -= 1
        return out

    def group(self) -> str:
        if self.peek() != "{":
            raise self.err("expected '{'")
        self.i += 1
        items = self.seq("}")
        if self.peek() != "}":
            raise self.err("unbalanced '{'")
        self.i += 1
        return "<mrow>" + "".join(items) + "</mrow>"

    def script(self) -> str:
        c = self.peek()
        if c == "{":
            return self.group()
        if c == "(":
            return self.paren()
        m = re.compile(r"[-−]?\d+|[A-Za-z]|π").match(self.s, self.i)
        if m:
            self.i = m.end()
            t = m.group(0)
            if t[0] in "-−":
                return f"<mrow><mo>−</mo><mn>{t[1:]}</mn></mrow>"
            return f"<mn>{t}</mn>" if t.isdigit() else f"<mi>{_xml_escape(t)}</mi>"
        if c == "\\":
            m = _CMD_RE.match(self.s, self.i)
            if m and m.group(1) in ("circ", "degree"):
                self.i = m.end()
                return "<mo>°</mo>"
            if m and m.group(1) == "pi":
                self.i = m.end()
                return "<mi>π</mi>"
        raise self.err("bad exponent or subscript")

    def paren(self) -> str:
        open_, close = ("(", ")") if self.peek() == "(" else ("[", "]")
        self.i += 1
        items = self.seq(close)
        if self.peek() != close:
            raise self.err("unbalanced parenthesis")
        self.i += 1
        return f"<mrow><mo>{open_}</mo>{''.join(items)}<mo>{close}</mo></mrow>"

    def base(self) -> tuple[list[str], bool, bool]:
        """Return (nodes, is_number, is_simple_for_fraction)."""
        c = self.peek()
        s = self.s
        m = _MML_NUM.match(s, self.i)
        if m:
            self.i = m.end()
            return [f"<mn>{_xml_escape(m.group(0))}</mn>"], True, True
        if c in "([":
            return [self.paren()], False, False
        if c == "{":
            return [self.group()], False, False
        if c == "√":
            self.i += 1
            self.ws()
            nodes, _ = self.postfix_no_frac()
            return [f"<msqrt>{''.join(nodes)}</msqrt>"], False, False
        if c == "\\":
            m = _CMD_RE.match(s, self.i)
            if not m:
                raise self.err("bad command")
            cmd = m.group(1)
            self.i = m.end()
            if cmd in ("frac", "dfrac", "tfrac"):
                self.ws()
                a = self.group()
                self.ws()
                b = self.group()
                return [f"<mfrac>{a}{b}</mfrac>"], False, False
            if cmd == "sqrt":
                self.ws()
                if self.peek() == "[":
                    k = s.find("]", self.i)
                    if k < 0:
                        raise self.err("unbalanced '['")
                    idx = _MathMLParser(s[self.i + 1:k]).parse_all()
                    self.i = k + 1
                    self.ws()
                    return [f"<mroot>{self.group()}<mrow>{idx}</mrow></mroot>"], False, False
                return [f"<msqrt>{self.group()}</msqrt>"], False, False
            if cmd == "pi":
                return ["<mi>π</mi>"], False, False
            raise self.err(f"command \\{cmd} not supported")
        if c == "π":
            self.i += 1
            return ["<mi>π</mi>"], False, False
        if c.isalpha():
            m = re.compile(r"[^\W\d_²³¹⁰-⁹]+").match(s, self.i)
            word = m.group(0)
            self.i = m.end()
            if word in _MML_FUNCS:
                return [f"<mi>{word}</mi>"], False, False
            if word in _MML_UNITS and self._after_number():
                return [f'<mi mathvariant="normal">{word}</mi>'], False, False
            if len(word) == 1:
                return [f"<mi>{_xml_escape(word)}</mi>"], False, True
            if word.isupper() and len(word) <= 3:
                return [f"<mi>{_xml_escape(word)}</mi>"], False, False
            if len(word) > 3:
                raise self.err(f"word {word!r} is not a math identifier")
            # sequence of single-letter variables: implicit multiplication; keep last letter for scripts
            nodes: list[str] = []
            for k, ch in enumerate(word):
                if k:
                    nodes.append("<mo>&#x2062;</mo>")
                nodes.append(f"<mi>{_xml_escape(ch)}</mi>")
            return nodes, False, False
        raise self.err(f"character {c!r} not supported")

    def _after_number(self) -> bool:
        before = self.s[:self.i].rstrip(" \u00a0")
        # the unit word was consumed; look at what precedes it
        word_start = re.search(r"[^\W\d_]+$", self.s[:self.i])
        if not word_start:
            return False
        before = self.s[:word_start.start()].rstrip(" \u00a0\u202f")
        return bool(re.search(r"\d$|[²³]$", before)) or bool(re.search(r"\d\s*$", before))

    def postfix_no_frac(self) -> tuple[list[str], bool]:
        nodes, is_num, _ = self.base()
        return self._suffixes(nodes, is_num)

    def _suffixes(self, nodes: list[str], is_num: bool) -> tuple[list[str], bool]:
        sub = sup = None
        while True:
            c = self.peek()
            if c == "^":
                self.i += 1
                sup = self.script()
            elif c == "_":
                self.i += 1
                sub = self.script()
            elif c in ("²", "³"):
                self.i += 1
                sup = f"<mn>{'2' if c == '²' else '3'}</mn>"
            else:
                break
        if sub is not None or sup is not None:
            core = nodes[-1]
            head = nodes[:-1]
            if sub is not None and sup is not None:
                node = f"<msubsup>{core}{sub}{sup}</msubsup>"
            elif sup is not None:
                node = f"<msup>{core}{sup}</msup>"
            else:
                node = f"<msub>{core}{sub}</msub>"
            nodes = head + [node]
            is_num = False
        while self.peek() in ("°", "%") and self.peek():
            nodes = nodes + [f"<mo>{self.peek()}</mo>"]
            self.i += 1
            is_num = False
        return nodes, is_num

    def postfix(self) -> tuple[list[str], bool]:
        start = self.i
        nodes, is_num, simple = self.base()
        if simple and self.peek() not in ("^", "_", "²", "³"):
            m = _MML_SIMPLE_FRAC.match(self.s, self.i)
            if m:
                self.i = m.end()
                den = m.group(1)
                den_node = f"<mn>{den}</mn>" if den[0].isdigit() else f"<mi>{_xml_escape(den)}</mi>"
                return [f"<mfrac>{nodes[0]}{den_node}</mfrac>"], False
        return self._suffixes(nodes, is_num)

    def parse_all(self) -> str:
        items = self.seq("")
        if self.i < len(self.s):
            raise self.err("unexpected character")
        if not items:
            raise ValueError("empty expression")
        return "".join(items)


def to_mathml(expr: str, lang: str = "fr") -> str:
    """Presentation MathML for a safe subset; raises ValueError otherwise."""
    if not isinstance(expr, str) or not expr.strip():
        raise ValueError("empty expression")
    if len(expr) > 400:
        raise ValueError("expression too long")
    src = expr.strip()
    if src.startswith("$") and src.endswith("$") and len(src) > 1:
        src = src.strip("$").strip()
    body = _MathMLParser(src).parse_all()
    alt = _xml_escape(spoken_math(src, lang), {'"': "&quot;"})
    return f'<math xmlns="http://www.w3.org/1998/Math/MathML" alttext="{alt}"><mrow>{body}</mrow></math>'


# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Finding:
    """One deterministic accessibility finding."""
    code: str
    severity: str
    message_fr: str
    message_en: str
    span: Optional[tuple[int, int]] = None


@dataclass(frozen=True)
class AdaptedReply:
    """Result of adapt(): adapted text, speech form, MathML and an audit."""
    text: str
    spoken: Optional[str]
    mathml: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


_MSG = {
    "LONG_SENTENCE": ("Phrase trop longue ({n} mots, maximum {max}) : la couper en phrases plus courtes.",
                      "Sentence too long ({n} words, maximum {max}): split it into shorter sentences."),
    "TOO_MANY_STEPS": ("Trop d'étapes dans un seul message ({n}, maximum {max}) : une étape à la fois.",
                       "Too many steps in one message ({n}, maximum {max}): one step at a time."),
    "TOO_MANY_QUESTIONS": ("Trop de questions dans un seul message ({n}, maximum {max}).",
                           "Too many questions in one message ({n}, maximum {max})."),
    "FIGURATIVE": ("Expression imagée « {t} » : dire littéralement ce qui est attendu.",
                   "Figurative expression \"{t}\": say literally what is expected."),
    "TIME_PRESSURE": ("Pression de temps « {t} » : supprimer ou reformuler sans urgence.",
                      "Time pressure \"{t}\": remove or rephrase without urgency."),
    "SYMBOL_UNEXPLAINED": ("Symbole « {t} » non expliqué, mal lu par un lecteur d'écran : l'écrire en mots.",
                           "Symbol \"{t}\" unexplained and poorly read by screen readers: write it in words."),
    "ASCII_ART": ("Dessin ou séparateur en caractères : illisible au lecteur d'écran, le remplacer par une description.",
                  "Character drawing or separator: unreadable by screen readers, replace it with a description."),
    "TABLE": ("Tableau en texte : difficile à parcourir à la voix, préférer des phrases ou une liste.",
              "Text table: hard to navigate by voice, prefer sentences or a list."),
    "EMOJI_EXCESS": ("Trop d'emoji ({n}, maximum {max}).", "Too many emoji ({n}, maximum {max})."),
    "COLOR_ONLY": ("Référence par la couleur seule « {t} » : ajouter un nom, une forme ou une position écrite.",
                   "Colour-only reference \"{t}\": add a name, shape or written position."),
    "VISUAL_DEIXIS": ("Renvoi purement visuel « {t} » : décrire ce qu'il faut voir avec des mots.",
                      "Visual-only pointer \"{t}\": describe what to look at in words."),
    "AUDIO_ONLY_CUE": ("Indice sonore « {t} » : fournir l'information par écrit.",
                       "Audio-only cue \"{t}\": provide the information in writing."),
    "CAPS_SHOUTING": ("Mot en majuscules « {t} » : ton perçu comme un cri, écrire en minuscules.",
                      "ALL-CAPS word \"{t}\": reads as shouting, write in lower case."),
    "LONG_PARAGRAPH": ("Paragraphe trop long d'un seul bloc ({n} mots) : aérer et couper.",
                       "Very long unbroken paragraph ({n} words): add breaks."),
    "RAW_LATEX": ("LaTeX brut « {t} » : le rendre en MathML ou en texte parlé pour la sortie vocale.",
                  "Raw LaTeX \"{t}\": render it as MathML or spoken text for speech output."),
    "TYPING_HEAVY": ("Demande de saisie lourde « {t} » : proposer un choix ou une réponse courte.",
                     "Typing-heavy request \"{t}\": offer a choice or a short answer."),
}


def _mk(code: str, severity: str, span: Optional[tuple[int, int]] = None, **kw) -> Finding:
    fr, en = _MSG[code]
    return Finding(code, severity, fr.format(**kw), en.format(**kw), span)


@lru_cache(maxsize=1)
def _lexicons() -> dict:
    path = Path(__file__).with_name("access_data") / "lexicons.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _phrase_regex(phrases: list[str]) -> "re.Pattern[str]":
    parts = []
    for p in sorted(set(phrases), key=len, reverse=True):
        e = re.escape(p.lower()).replace("\\ ", r"\s+").replace("'", "['’]")
        parts.append(e)
    return re.compile(r"(?<![\w])(?:" + "|".join(parts) + r")(?![\w])", re.I)


@lru_cache(maxsize=None)
def _lex_re(key: str, lang: str) -> "re.Pattern[str]":
    return _phrase_regex(_lexicons()[key][lang])


@lru_cache(maxsize=None)
def _color_res(lang: str) -> tuple["re.Pattern[str]", ...]:
    lex = _lexicons()
    colors = "|".join(sorted(map(re.escape, lex["color_words"][lang]), key=len, reverse=True))
    nouns = "|".join(sorted(map(re.escape, lex["color_nouns"][lang]), key=len, reverse=True))
    if lang == "fr":
        return (re.compile(rf"(?<![\w])(?:{nouns})\s+(?:\w+\s+)?(?:{colors})(?![\w])", re.I),
                re.compile(rf"(?<![\w])en\s+(?:{colors})(?![\w])", re.I))
    return (re.compile(rf"(?<![\w])(?:{colors})\s+(?:{nouns})(?![\w])", re.I),
            re.compile(rf"(?<![\w])in\s+(?:{colors})(?![\w])", re.I))


_WORD_RE = re.compile(r"\d+(?:[.,]\d+)+|[^\W_]+(?:['’\-][^\W_]+)*")
_TERMINATORS = ".!?…"
_EMOJI_ONE = (r"(?:[\U0001F1E6-\U0001F1FF]{2}|[0-9#*]\uFE0F?\u20E3|"
              r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B50\u2B55\u2B1B\u2B1C\u231A\u231B\u23E9-\u23F3\u23F8-\u23FA]"
              r"[\uFE0F\U0001F3FB-\U0001F3FF]*(?:\u200D[\U0001F000-\U0001FAFF\u2600-\u27BF][\uFE0F\U0001F3FB-\U0001F3FF]*)*)")
_EMOJI_RE = re.compile(_EMOJI_ONE)
_SYMBOL_RE = re.compile("[\u2190-\u21FF\u2234\u2235\u2248\u27F0-\u27FF\u2900-\u297F\u25A0-\u25FF\u2500-\u259F]")
_ASCII_ARROW_RE = re.compile(r"(?<=\s)(?:-{1,3}>|={1,3}>|<-{1,3})(?=\s)")
_STEP_LINE_RE = re.compile(r"^[ \t]*[*_]*(?:\d{1,2}\s*[.)]|[-*•]|étape\s*\d+|step\s*\d+)(?=\s)", re.I | re.M)
_STEP_INLINE_RE = re.compile(r"\b(?:étape|step)\s*\d+", re.I)
_LATEX_RAW_RE = re.compile(r"\\[A-Za-z]{2,}|\$[^$\n]+\$|\^\{|_\{")
_CAPS_RE = re.compile(r"(?<![\w$\\])[A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ]{4,}(?![\w])")
_NEGATION_RE = re.compile(r"\b(?:pas|sans|jamais|inutile|besoin|not|no|don'?t|do not|without|never)\b[^.!?\n]{0,25}$", re.I)


def count_words(s: str) -> int:
    """Words in a string (hyphenated and apostrophe words count once)."""
    return len(_WORD_RE.findall(s))


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    n, start, i = len(text), 0, 0

    def add(a: int, b: int) -> None:
        seg = text[a:b]
        if seg.strip():
            lead = len(seg) - len(seg.lstrip())
            spans.append((a + lead, a + len(seg.rstrip())))

    while i < n:
        c = text[i]
        if c == "\n":
            add(start, i)
            start = i + 1
        elif c in _TERMINATORS:
            j = i
            while j < n and text[j] in _TERMINATORS:
                j += 1
            if (j == n or text[j].isspace()) and not re.fullmatch(r"\s*\d{1,2}", text[start:i]):
                add(start, j)
                start = j
            i = j - 1
        i += 1
    add(start, n)
    return spans


def _lint_lexical(text: str, key: str, lang: str, code: str, sev: str, out: list[Finding], neg: bool = False) -> None:
    for m in _lex_re(key, lang).finditer(text):
        if neg and _NEGATION_RE.search(text[max(0, m.start() - 40):m.start()]):
            continue
        out.append(_mk(code, sev, m.span(), t=m.group(0)))


def lint(reply: str, profile: Union[Profile, str], lang: str = "fr") -> list[Finding]:
    """Deterministic profile-driven accessibility checks on a tutor reply."""
    p = get_profile(profile)
    lang = _lang(lang)
    out: list[Finding] = []
    text = reply

    if p.max_sentence_words is not None:
        for a, b in _sentence_spans(text):
            nw = count_words(text[a:b])
            if nw > p.max_sentence_words:
                out.append(_mk("LONG_SENTENCE", "warn", (a, b), n=nw, max=p.max_sentence_words))

    if p.max_steps_per_reply is not None:
        steps = max(len(_STEP_LINE_RE.findall(text)), len(_STEP_INLINE_RE.findall(text)))
        if steps > p.max_steps_per_reply:
            out.append(_mk("TOO_MANY_STEPS", "warn", None, n=steps, max=p.max_steps_per_reply))
        q = len(re.findall(r"\?(?!\w)", text))
        if q > p.max_steps_per_reply:
            out.append(_mk("TOO_MANY_QUESTIONS", "warn", None, n=q, max=p.max_steps_per_reply))

    if p.forbid_figurative:
        _lint_lexical(text, "figurative", lang, "FIGURATIVE", "warn", out)
    if p.forbid_time_pressure:
        _lint_lexical(text, "time_pressure", lang, "TIME_PRESSURE", "warn", out, neg=True)

    if p.limit_symbols or p.spoken_math:
        for m in _SYMBOL_RE.finditer(text):
            if p.limit_symbols and not (0x2500 <= ord(m.group(0)) <= 0x259F):
                out.append(_mk("SYMBOL_UNEXPLAINED", "warn", m.span(), t=m.group(0)))
        for m in _ASCII_ARROW_RE.finditer(text):
            out.append(_mk("SYMBOL_UNEXPLAINED", "warn", m.span(), t=m.group(0)))
        for m in re.finditer(r"[\u2500-\u259F]+", text):
            out.append(_mk("ASCII_ART", "warn", m.span()))
        pos = 0
        pipe_lines = 0
        for line in text.split("\n"):
            stripped = line.strip()
            alnum = sum(c.isalnum() for c in stripped)
            if re.fullmatch(r"[-=_*#~+|/\\:]{4,}", stripped) or re.fullmatch(r"\+[-=+]{3,}\+?", stripped) or (
                    len(stripped) >= 8 and alnum <= len(stripped) * 0.2 and not re.search(r"[A-Za-z]{2}", stripped)
                    and re.search(r"[_/\\|()<>^'`.-]{4,}", stripped)):
                out.append(_mk("ASCII_ART", "warn", (pos, pos + len(line))))
            if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 3:
                pipe_lines += 1
                if pipe_lines == 2:
                    out.append(_mk("TABLE", "warn", (pos, pos + len(line))))
            else:
                pipe_lines = 0
            pos += len(line) + 1

    if p.limit_emoji is not None:
        found = list(_EMOJI_RE.finditer(text))
        if len(found) > p.limit_emoji:
            out.append(_mk("EMOJI_EXCESS", "warn", (found[p.limit_emoji].start(), found[-1].end()), n=len(found), max=p.limit_emoji))

    for rx in _color_res(lang):
        for m in rx.finditer(text):
            out.append(_mk("COLOR_ONLY", "warn", m.span(), t=m.group(0)))

    if {"lecture_ecran", "vision_reduite"} & set(p.needs):
        sev = "warn" if "lecture_ecran" in p.needs else "info"
        _lint_lexical(text, "visual_deixis", lang, "VISUAL_DEIXIS", sev, out)
    if "texte_prioritaire" in p.needs:
        _lint_lexical(text, "audio_cues", lang, "AUDIO_ONLY_CUE", "warn", out)
    if "motricite_fine" in p.needs:
        _lint_lexical(text, "typing_heavy", lang, "TYPING_HEAVY", "warn", out)

    allow = set(_lexicons()["caps_allowlist"]) | _ACRONYMS
    for m in _CAPS_RE.finditer(text):
        w = m.group(0)
        if w in allow or list(w) == sorted(w):
            continue
        out.append(_mk("CAPS_SHOUTING", "info", m.span(), t=w))

    limit = 70 if p.max_sentence_words is not None else 140
    pos = 0
    for para in re.split(r"\n\s*\n", text):
        idx = text.find(para, pos)
        pos = idx + len(para)
        if "\n" not in para.strip() and count_words(para) > limit:
            out.append(_mk("LONG_PARAGRAPH", "info", (idx, idx + len(para)), n=count_words(para)))

    if p.spoken_math:
        m = _LATEX_RAW_RE.search(text)
        if m:
            out.append(_mk("RAW_LATEX", "warn", m.span(), t=m.group(0)))
    return out


# ---------------------------------------------------------------------------
# Adapt
# ---------------------------------------------------------------------------

_ADAPT_MSG = {
    "ADAPT_EMOJI_REMOVED": ("{n} emoji retiré(s) pour respecter la limite du profil.", "{n} emoji removed to respect the profile limit."),
    "ADAPT_STEP_LINEBREAK": ("{n} étape(s) placée(s) sur leur propre ligne.", "{n} step(s) moved onto their own line."),
    "ADAPT_SENTENCE_SPLIT": ("{n} phrase(s) longue(s) coupée(s) à une conjonction sûre.", "{n} long sentence(s) split at a safe conjunction."),
    "ADAPT_SPOKEN_FORM": ("Forme parlée générée pour la synthèse vocale.", "Spoken form generated for speech output."),
    "ADAPT_MATHML": ("{n} expression(s) convertie(s) en MathML.", "{n} expression(s) converted to MathML."),
    "ADAPT_MATHML_SKIPPED": ("Expression non convertie en MathML (hors sous-ensemble) : « {t} ».", "Expression not converted to MathML (outside the subset): \"{t}\"."),
}


def _audit(code: str, **kw) -> Finding:
    fr, en = _ADAPT_MSG[code]
    return Finding(code, "info", fr.format(**kw), en.format(**kw), None)


_CONJ = {
    "fr": (["mais", "puis", "donc", "car", "ensuite", "alors", "or"], ["et", "ou"]),
    "en": (["but", "then", "so", "because", "while"], ["and", "or"]),
}


def _balanced(s: str) -> bool:
    return s.count("(") == s.count(")") and s.count("$") % 2 == 0 and s.count("{") == s.count("}")


def _split_sentence(sent: str, limit: int, lang: str, depth: int = 0) -> str:
    if count_words(sent) <= limit or depth > 4:
        return sent
    strong, weak = _CONJ[lang]
    cands: list[tuple[int, int, str, bool]] = []
    for m in re.finditer(r",\s+(" + "|".join(strong + weak) + r")\s+", sent, re.I):
        cands.append((m.start(), m.end(), m.group(1), m.group(1).lower() in weak))
    for m in re.finditer(r";\s+", sent):
        cands.append((m.start(), m.end(), "", False))
    best = None
    total = count_words(sent)
    for a, b, conj, is_weak in cands:
        left, right = sent[:a], conj + (" " if conj else "") + sent[b:]
        lw, rw = count_words(left), count_words(right)
        if lw < 3 or rw < 3 or not _balanced(left):
            continue
        if is_weak and (left.count(",") > 0 or lw < 5 or rw < 5):
            continue
        score = abs(lw - rw) + (3 if is_weak else 0)
        if best is None or score < best[0]:
            best = (score, a, b, conj)
    if best is None:
        return sent
    _, a, b, conj = best
    left = sent[:a].rstrip()
    right = (conj + " " if conj else "") + sent[b:]
    right = right[:1].upper() + right[1:]
    if left and left[-1] not in _TERMINATORS:
        left += "."
    return _split_sentence(left, limit, lang, depth + 1) + " " + _split_sentence(right, limit, lang, depth + 1)


def _limit_emoji(text: str, limit: int) -> tuple[str, int]:
    kept = [0]
    removed = [0]

    def rep(m: re.Match) -> str:
        if kept[0] < limit:
            kept[0] += 1
            return m.group(0)
        removed[0] += 1
        return ""
    new = _EMOJI_RE.sub(rep, text)
    if removed[0]:
        new = re.sub(r"(?m)[ \t]+(?=[,.;]|$)", "", new)
        new = re.sub(r"(?<=\S)[ \t]{2,}", " ", new)
    return new, removed[0]


_MATH_FRAG_RE = re.compile(r"\$\$(.+?)\$\$|\$([^$\n]+)\$|\\\((.+?)\\\)|\\\[(.+?)\\\]", re.S)


def _math_fragments(text: str) -> list[str]:
    frags = [next(g for g in m.groups() if g is not None).strip() for m in _MATH_FRAG_RE.finditer(text)]
    for line in text.split("\n"):
        s = line.strip().rstrip(".")
        if (len(s) >= 3 and re.search(r"[=≤≥≠≈<>]", s) and not re.search(r"[A-Za-zÀ-ÿ]{4,}", s.replace("\\", ""))
                and not _MATH_FRAG_RE.search(s) and re.fullmatch(r"[\w\s+\-−×÷*/^()=<>≤≥≠≈√π²³.,°%]+", s)):
            frags.append(s)
    return frags


def adapt(reply: str, profile: Union[Profile, str], lang: str = "fr") -> AdaptedReply:
    """Conservative deterministic adaptation; never changes mathematical content."""
    p = get_profile(profile)
    lang = _lang(lang)
    audit: list[Finding] = []
    text = reply.replace("\r\n", "\n")

    if p.limit_emoji is not None:
        text, removed = _limit_emoji(text, p.limit_emoji)
        if removed:
            audit.append(_audit("ADAPT_EMOJI_REMOVED", n=removed))

    if p.max_steps_per_reply is not None:
        text, k = re.subn(r"(?<=[.!?:;])[ \t]+(?=(?:\d{1,2}[.)]|[ÉEé]tape\s*\d+|Step\s*\d+)[ \t]+\S)", "\n", text)
        if k:
            audit.append(_audit("ADAPT_STEP_LINEBREAK", n=k))

    if p.max_sentence_words is not None:
        pieces: list[str] = []
        pos, changed = 0, 0
        for a, b in _sentence_spans(text):
            new = _split_sentence(text[a:b], p.max_sentence_words, lang)
            if new != text[a:b]:
                changed += 1
            pieces.append(text[pos:a] + new)
            pos = b
        pieces.append(text[pos:])
        text = "".join(pieces)
        if changed:
            audit.append(_audit("ADAPT_SENTENCE_SPLIT", n=changed))

    spoken: Optional[str] = None
    mathml: list[str] = []
    if p.spoken_math:
        plain = _EMOJI_RE.sub("", text).replace("\uFE0F", "")
        lines = []
        for line in plain.split("\n"):
            line = line.strip()
            if line and line[-1] not in _TERMINATORS + ":;,":
                line += "."
            if line:
                lines.append(line)
        spoken = spoken_math(" ".join(lines), lang, "explicit")
        audit.append(_audit("ADAPT_SPOKEN_FORM"))
        for frag in _math_fragments(text):
            try:
                mathml.append(to_mathml(frag, lang))
            except ValueError:
                audit.append(_audit("ADAPT_MATHML_SKIPPED", t=frag[:60]))
        if mathml:
            audit.append(_audit("ADAPT_MATHML", n=len(mathml)))

    findings = lint(text, p, lang) + audit
    return AdaptedReply(text=text, spoken=spoken, mathml=mathml, findings=findings)


# ---------------------------------------------------------------------------
# Prompt addendum and explanations
# ---------------------------------------------------------------------------

def profile_prompt_addendum(profile: Union[Profile, str], lang: str = "fr") -> str:
    """Instruction text to append to the LLM system prompt for this profile."""
    p = get_profile(profile)
    lang = _lang(lang)
    if p.name == "default" and not p.needs:
        return ""
    fr = lang == "fr"
    L: list[str] = []
    L.append(
        "Adaptation d'accessibilité (préférences de présentation choisies, jamais un diagnostic : ne demande, ne devine "
        "et ne mentionne jamais un handicap ou une difficulté de l'élève). Le contrat pédagogique ne change pas : "
        "donne des indices, jamais la réponse finale."
        if fr else
        "Accessibility adaptation (presentation preferences that were chosen, never a diagnosis: never ask about, guess "
        "or mention a disability or difficulty of the pupil). The pedagogical contract is unchanged: give hints, "
        "never the final answer.")
    if p.max_sentence_words:
        L.append(f"Phrases de {p.max_sentence_words} mots maximum." if fr else f"Sentences of at most {p.max_sentence_words} words.")
    if p.max_steps_per_reply == 1:
        L.append("Une seule étape et une seule question par message." if fr else "One step and one question per message.")
    elif p.max_steps_per_reply:
        L.append(f"{p.max_steps_per_reply} étapes au maximum par message, chacune sur sa ligne." if fr
                 else f"At most {p.max_steps_per_reply} steps per message, each on its own line.")
    if p.forbid_figurative:
        L.append("Pas d'expression imagée, d'ironie ni de sous-entendu : dis exactement ce que tu veux dire." if fr
                 else "No figures of speech, irony or implied meaning: say exactly what you mean.")
    if p.forbid_time_pressure:
        L.append("Aucune pression de temps : n'écris jamais « vite », « rapidement », « chrono » ; dis que l'élève peut prendre son temps." if fr
                 else "No time pressure: never write \"hurry\", \"quickly\", \"fast\"; say the pupil can take their time.")
    if p.spoken_math:
        L.append("Écris les maths pour être lues à voix haute : un calcul par ligne, le signe moins « − » entouré d'espaces, "
                 "fractions en a/b ou \\frac{a}{b}, pas de tableau." if fr else
                 "Write maths so they can be read aloud: one calculation per line, the minus sign \"−\" surrounded by spaces, "
                 "fractions as a/b or \\frac{a}{b}, no table.")
    if p.limit_symbols:
        L.append("Pas de flèche, de symbole décoratif, de dessin en caractères ni de tableau : utilise des mots." if fr
                 else "No arrows, decorative symbols, character drawings or tables: use words.")
    if p.limit_emoji == 0:
        L.append("Pas d'emoji." if fr else "No emoji.")
    elif p.limit_emoji:
        L.append(f"{p.limit_emoji} emoji au maximum." if fr else f"At most {p.limit_emoji} emoji.")
    L.append("Ne désigne jamais un élément par sa couleur ou sa position seule (« la case rouge », « ci-dessus ») : nomme-le." if fr
             else "Never refer to something by colour or position alone (\"the red box\", \"above\"): name it.")
    if "texte_prioritaire" in p.needs:
        L.append("Toute information doit être écrite ; ne t'appuie jamais sur un son ou une consigne orale seule." if fr
                 else "Every piece of information must be written; never rely on sound or an oral instruction alone.")
    if "motricite_fine" in p.needs:
        L.append("Propose des réponses courtes : un nombre, un mot ou un choix parmi 2 à 4 options ; pas de longue rédaction." if fr
                 else "Ask for short answers: a number, a word or a choice among 2 to 4 options; no long writing.")
    if "previsibilite" in p.needs:
        L.append("Même structure à chaque message : 1) ce qu'on fait, 2) la consigne, 3) la question." if fr
                 else "Same structure in every message: 1) what we are doing, 2) the instruction, 3) the question.")
    if "charge_cognitive" in p.needs:
        L.append("Une idée par phrase ; ne répète pas l'énoncé en entier." if fr
                 else "One idea per sentence; do not repeat the whole problem statement.")
    if "lecture_fluente" in p.needs:
        L.append("Mots courants, paragraphes de 3 lignes au plus." if fr else "Common words, paragraphs of at most 3 lines.")
    if "vision_reduite" in p.needs:
        L.append("Va à la ligne souvent ; ne dépend d'aucun détail de mise en forme pour être compris." if fr
                 else "Break lines often; do not depend on any formatting detail to be understood.")
    return "\n".join("- " + x if i else x for i, x in enumerate(L))


def explain_profile(profile: Union[Profile, str], lang: str = "fr") -> str:
    """Plain-language explanation of the preference bundle for a teacher or parent."""
    p = get_profile(profile)
    lang = _lang(lang)
    fr = lang == "fr"
    idx = 0 if fr else 1
    label = p.label_fr if fr else p.label_en
    lines: list[str] = []
    if fr:
        lines.append(f"Profil « {label} » ({p.name}). C'est un ensemble de préférences de présentation, pas un diagnostic : "
                     "il est choisi par l'élève, un parent ou l'enseignant, rangé sur l'appareil et jamais déduit des messages de l'élève.")
        if p.needs:
            lines.append("Besoins couverts : " + " ; ".join(NEEDS[n][idx] for n in p.needs) + ".")
        else:
            lines.append("Aucune adaptation : les réponses restent telles que le tuteur les écrit.")
        if p.max_sentence_words:
            lines.append(f"Phrases de {p.max_sentence_words} mots au plus.")
        if p.max_steps_per_reply:
            lines.append("Une seule étape par message." if p.max_steps_per_reply == 1 else f"Jusqu'à {p.max_steps_per_reply} étapes par message.")
        if p.forbid_figurative:
            lines.append("Pas d'expressions imagées (« ça roule », « coup de main »).")
        if p.forbid_time_pressure:
            lines.append("Aucune pression de temps (« vite », « chrono »).")
        if p.spoken_math:
            lines.append("Les maths sont aussi fournies sous forme parlée (« trois sur quatre ») et en MathML.")
        if p.limit_symbols:
            lines.append("Pas de flèches, dessins en caractères ni tableaux en texte.")
        if p.limit_emoji is not None:
            lines.append("Aucun emoji." if p.limit_emoji == 0 else f"{p.limit_emoji} emoji au plus.")
        lines.append("Le contrat pédagogique est inchangé : indices, jamais la réponse finale.")
    else:
        lines.append(f"Profile \"{label}\" ({p.name}). It is a bundle of presentation preferences, not a diagnosis: "
                     "it is chosen by the pupil, a parent or the teacher, stored on the device and never inferred from the pupil's messages.")
        if p.needs:
            lines.append("Needs covered: " + "; ".join(NEEDS[n][idx] for n in p.needs) + ".")
        else:
            lines.append("No adaptation: replies stay as the tutor writes them.")
        if p.max_sentence_words:
            lines.append(f"Sentences of at most {p.max_sentence_words} words.")
        if p.max_steps_per_reply:
            lines.append("One step per message." if p.max_steps_per_reply == 1 else f"Up to {p.max_steps_per_reply} steps per message.")
        if p.forbid_figurative:
            lines.append("No figures of speech (\"piece of cake\", \"give a hand\").")
        if p.forbid_time_pressure:
            lines.append("No time pressure (\"hurry\", \"quickly\").")
        if p.spoken_math:
            lines.append("Maths are also provided as spoken text (\"three over four\") and as MathML.")
        if p.limit_symbols:
            lines.append("No arrows, character drawings or text tables.")
        if p.limit_emoji is not None:
            lines.append("No emoji." if p.limit_emoji == 0 else f"At most {p.limit_emoji} emoji.")
        lines.append("The pedagogical contract is unchanged: hints, never the final answer.")
    return " ".join(lines)
