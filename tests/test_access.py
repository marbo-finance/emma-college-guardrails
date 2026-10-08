"""Tests for emma_college.access (accessibility layer). stdlib unittest only."""
from __future__ import annotations

import dataclasses
import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from emma_college import access  # noqa: E402
from emma_college.access import (  # noqa: E402
    PROFILES, NEEDS, Finding, Profile, adapt, combine_profiles, en_number, explain_profile, fr_number,
    lint, profile_prompt_addendum, spoken_math, to_mathml,
)

CORPUS = ROOT / "corpus-access" / "accessibility-cases.jsonl"
MML = "{http://www.w3.org/1998/Math/MathML}"


def codes(reply: str, profile: str, lang: str = "fr") -> set[str]:
    return {f.code for f in lint(reply, profile, lang)}


class TestFrenchNumbers(unittest.TestCase):
    CASES = {
        0: "zéro", 1: "un", 2: "deux", 9: "neuf", 10: "dix", 11: "onze", 16: "seize", 17: "dix-sept",
        19: "dix-neuf", 20: "vingt", 21: "vingt et un", 22: "vingt-deux", 30: "trente", 31: "trente et un",
        41: "quarante et un", 51: "cinquante et un", 60: "soixante", 61: "soixante et un",
        69: "soixante-neuf", 70: "soixante-dix", 71: "soixante et onze", 72: "soixante-douze",
        77: "soixante-dix-sept", 79: "soixante-dix-neuf", 80: "quatre-vingts", 81: "quatre-vingt-un",
        85: "quatre-vingt-cinq", 90: "quatre-vingt-dix", 91: "quatre-vingt-onze", 99: "quatre-vingt-dix-neuf",
        100: "cent", 101: "cent un", 111: "cent onze", 121: "cent vingt et un", 180: "cent quatre-vingts",
        199: "cent quatre-vingt-dix-neuf", 200: "deux cents", 201: "deux cent un", 280: "deux cent quatre-vingts",
        300: "trois cents", 999: "neuf cent quatre-vingt-dix-neuf", 1000: "mille", 1001: "mille un",
        1080: "mille quatre-vingts", 1100: "mille cent", 1981: "mille neuf cent quatre-vingt-un",
        2000: "deux mille", 2026: "deux mille vingt-six", 21000: "vingt et un mille",
        80000: "quatre-vingt mille", 81000: "quatre-vingt-un mille", 200000: "deux cent mille",
        280000: "deux cent quatre-vingt mille", 999999: "neuf cent quatre-vingt-dix-neuf mille neuf cent quatre-vingt-dix-neuf",
        1000000: "un million", 2000000: "deux millions", 80000000: "quatre-vingts millions", -7: "moins sept",
    }

    def test_table(self):
        for n, words in self.CASES.items():
            with self.subTest(n=n):
                self.assertEqual(fr_number(n), words)

    def test_every_integer_below_a_thousand_is_clean(self):
        for n in range(1000):
            w = fr_number(n)
            with self.subTest(n=n):
                self.assertRegex(w, r"^[a-zéèêîôûç \-]+$")
                self.assertNotIn("  ", w)
                self.assertFalse(w.endswith(" "))

    def test_et_un_only_where_correct(self):
        for n in range(1, 1000):
            w = fr_number(n)
            if " et un" in w:
                self.assertIn(n % 100, (21, 31, 41, 51, 61), n)
            if n % 100 == 81 or n % 100 == 91:
                self.assertNotIn(" et ", w)

    def test_cents_agreement(self):
        for n in range(1, 10):
            self.assertTrue(fr_number(n * 100).endswith("cents") or n == 1)
            self.assertFalse(fr_number(n * 100 + 5).endswith("cents"))
        self.assertEqual(fr_number(200000), "deux cent mille")


class TestEnglishNumbers(unittest.TestCase):
    def test_table(self):
        cases = {0: "zero", 7: "seven", 13: "thirteen", 21: "twenty-one", 40: "forty", 99: "ninety-nine",
                 100: "one hundred", 101: "one hundred one", 999: "nine hundred ninety-nine",
                 1000: "one thousand", 2026: "two thousand twenty-six", 100000: "one hundred thousand",
                 999999: "nine hundred ninety-nine thousand nine hundred ninety-nine", -3: "minus three"}
        for n, w in cases.items():
            with self.subTest(n=n):
                self.assertEqual(en_number(n), w)


class TestSpokenMathFrench(unittest.TestCase):
    CASES = {
        "x = 5": "x égale cinq",
        "−7": "moins sept",
        "-7": "moins sept",
        "(-3)": "parenthèse ouverte moins trois parenthèse fermée",
        "x²": "x au carré",
        "x³": "x au cube",
        "x^2": "x au carré",
        "x^3": "x au cube",
        "x^4": "x puissance quatre",
        "x^{10}": "x puissance dix",
        "x^{-2}": "x puissance moins deux",
        "10^3": "dix puissance trois",
        "2^2": "deux au carré",
        "x⁴": "x puissance quatre",
        "x⁻¹": "x puissance moins un",
        "√2": "racine carrée de deux",
        "\\sqrt{2}": "racine carrée de deux",
        "$\\sqrt{x}$": "racine carrée de x",
        "\\sqrt[3]{8}": "racine cubique de huit",
        "√(x+1)": "racine carrée de parenthèse ouverte x plus un parenthèse fermée",
        "AB = 5 cm": "A B égale cinq centimètres",
        "BC = 1 cm": "B C égale un centimètre",
        "35°": "trente-cinq degrés",
        "1°": "un degré",
        "20 °C": "vingt degrés Celsius",
        "\\widehat{ABC} = 90°": "angle A B C égale quatre-vingt-dix degrés",
        "∠ABC = 35^\\circ": "angle A B C égale trente-cinq degrés",
        "3/4": "trois sur quatre",
        "1/2": "un sur deux",
        "a/b": "a sur b",
        "\\frac{3}{4}": "trois sur quatre",
        "$\\frac{1}{2}$": "un sur deux",
        "\\frac{a+b}{2}": "la fraction de numérateur a plus b et de dénominateur deux",
        "(x+1)/(x−2)": "parenthèse ouverte x plus un parenthèse fermée sur parenthèse ouverte x moins deux parenthèse fermée",
        "2,5": "deux virgule cinq",
        "0,5": "zéro virgule cinq",
        "0,05": "zéro virgule zéro cinq",
        "3,14": "trois virgule quatorze",
        "3.14": "trois virgule quatorze",
        "1 000": "mille",
        "1 000": "mille",
        "12 345": "douze mille trois cent quarante-cinq",
        "1 250 000": "un million deux cent cinquante mille",
        "2 100 cm": "deux mille cent centimètres",
        "x ≤ 3": "x inférieur ou égal à trois",
        "x ≥ −2": "x supérieur ou égal à moins deux",
        "x < 7": "x inférieur à sept",
        "x > 0": "x supérieur à zéro",
        "a ≠ 0": "a différent de zéro",
        "x ≈ 3,14": "x environ égal à trois virgule quatorze",
        "x <= 3": "x inférieur ou égal à trois",
        "x >= 3": "x supérieur ou égal à trois",
        "x != 3": "x différent de trois",
        "3 × 4": "trois fois quatre",
        "3 * 4": "trois fois quatre",
        "12 ÷ 4": "douze divisé par quatre",
        "5 + 3": "cinq plus trois",
        "5 − 3": "cinq moins trois",
        "5 - 3": "cinq moins trois",
        "x - 3": "x moins trois",
        "= -2": "égale moins deux",
        "20 %": "vingt pour cent",
        "5%": "cinq pour cent",
        "5 €": "cinq euros",
        "1 €": "un euro",
        "5 m": "cinq mètres",
        "1 m": "un mètre",
        "2 kg": "deux kilogrammes",
        "1,5 kg": "un virgule cinq kilogramme",
        "0 kg": "zéro kilogramme",
        "3 L": "trois litres",
        "5 m²": "cinq mètres carrés",
        "1 m²": "un mètre carré",
        "2 cm³": "deux centimètres cubes",
        "50 km/h": "cinquante kilomètres par heure",
        "10 m/s": "dix mètres par seconde",
        "1 h": "une heure",
        "21 min": "vingt et une minutes",
        "2 h 30": "deux heures trente",
        "14h30": "quatorze heures trente",
        "(−3)²": "parenthèse ouverte moins trois parenthèse fermée au carré",
        "(a+b)^2": "parenthèse ouverte a plus b parenthèse fermée au carré",
        "(3 ; −2)": "parenthèse ouverte trois point-virgule moins deux parenthèse fermée",
        "f(2) = 5": "f de deux égale cinq",
        "π": "pi",
        "2π": "deux pi",
        "2\\pi r": "deux pi r",
        "3x² + 2x − 1 = 0": "trois x au carré plus deux x moins un égale zéro",
        "x_1": "x indice un",
        "1er": "premier",
        "1re": "première",
        "4e": "quatrième",
        "5e": "cinquième",
        "9e": "neuvième",
        "21e": "vingt et unième",
        "12/05/2026": "douze mai deux mille vingt-six",
        "01/01/2027": "premier janvier deux mille vingt-sept",
        "2026-10-08": "huit octobre deux mille vingt-six",
        "**Calcule** 3 * 4": "Calcule trois fois quatre",
        "Le périmètre vaut 4 × 5 = 20 cm.": "Le périmètre vaut quatre fois cinq égale vingt centimètres.",
    }

    def test_table(self):
        for src, want in self.CASES.items():
            with self.subTest(src=src):
                self.assertEqual(spoken_math(src, "fr"), want)

    def test_prose_is_untouched(self):
        for t in ["Il y a trois pommes.", "C'est peut-être vrai.", "Vingt-deux, v'là les flics !",
                  "Relis l'énoncé, puis réponds.", "Un e-mail à l'enseignant.", "Que vaut x ?"]:
            with self.subTest(t=t):
                self.assertEqual(spoken_math(t, "fr"), t)
        self.assertEqual(spoken_math("COVID-19 est un virus."), "COVID-dix-neuf est un virus.")

    def test_hyphenated_words_are_not_minus(self):
        self.assertNotIn("moins", spoken_math("c'est-à-dire peut-être est-ce"))

    def test_variables_next_to_digits_are_not_units(self):
        self.assertEqual(spoken_math("3t + 2"), "trois t plus deux")
        self.assertEqual(spoken_math("2m = 6"), "deux m égale six")
        self.assertEqual(spoken_math("4g"), "quatre g")

    def test_natural_style(self):
        cases = {"1/2": "un demi", "1/3": "un tiers", "2/3": "deux tiers", "1/4": "un quart", "3/4": "trois quarts",
                 "\\frac{3}{4}": "trois quarts", "5/6": "cinq sur six", "2/5": "deux sur cinq"}
        for src, want in cases.items():
            with self.subTest(src=src):
                self.assertEqual(spoken_math(src, "fr", style="natural"), want)
        self.assertEqual(spoken_math("3/4", "fr"), "trois sur quatre")  # explicit by default
        with self.assertRaises(ValueError):
            spoken_math("3/4", "fr", style="weird")

    def test_no_digits_or_math_symbols_survive(self):
        for src in self.CASES:
            out = spoken_math(src, "fr")
            with self.subTest(src=src):
                self.assertNotRegex(out, r"[0-9=+×÷≤≥≠≈√²³^\\$]||")

    def test_idempotent_on_spoken_text(self):
        for src in list(self.CASES)[:60]:
            once = spoken_math(src, "fr")
            self.assertEqual(spoken_math(once, "fr"), once, src)

    def test_beyond_range_falls_back_to_digits(self):
        self.assertEqual(spoken_math("12345678901"), "un deux trois quatre cinq six sept huit neuf zéro un")

    def test_unsupported_language(self):
        with self.assertRaises(ValueError):
            spoken_math("1", "de")


class TestSpokenMathEnglish(unittest.TestCase):
    CASES = {
        "x = 5": "x equals five",
        "−7": "minus seven",
        "x²": "x squared",
        "x³": "x cubed",
        "x^4": "x to the power of four",
        "x^{-2}": "x to the power of minus two",
        "√2": "square root of two",
        "\\sqrt{2}": "square root of two",
        "\\sqrt[3]{8}": "cube root of eight",
        "AB = 5 cm": "A B equals five centimeters",
        "35°": "thirty-five degrees",
        "1°": "one degree",
        "3/4": "three over four",
        "\\frac{3}{4}": "three over four",
        "\\frac{a+b}{2}": "the fraction with numerator a plus b and denominator two",
        "2.5": "two point five",
        "3.14": "three point one four",
        "1,000": "one point zero zero zero",
        "1 000": "one thousand",
        "x ≤ 3": "x less than or equal to three",
        "x ≥ 10": "x greater than or equal to ten",
        "a ≠ 0": "a not equal to zero",
        "x ≈ 3.14": "x approximately equal to three point one four",
        "3 × 4": "three times four",
        "12 ÷ 4": "twelve divided by four",
        "5 − 3": "five minus three",
        "20 %": "twenty percent",
        "5 €": "five euros",
        "1 m": "one meter",
        "5 m²": "five square meters",
        "50 km/h": "fifty kilometers per hour",
        "(−3)²": "open parenthesis minus three close parenthesis squared",
        "f(2) = 5": "f of two equals five",
        "3x² + 2x − 1 = 0": "three x squared plus two x minus one equals zero",
        "1st": "first", "2nd": "second", "3rd": "third", "4th": "fourth", "21st": "twenty-first",
        "12th": "twelfth", "30th": "thirtieth",
        "2026-10-08": "October eighth, twenty twenty-six",
    }

    def test_table(self):
        for src, want in self.CASES.items():
            with self.subTest(src=src):
                self.assertEqual(spoken_math(src, "en"), want)

    def test_natural_fractions(self):
        self.assertEqual(spoken_math("1/2", "en", style="natural"), "one half")
        self.assertEqual(spoken_math("3/4", "en", style="natural"), "three quarters")
        self.assertEqual(spoken_math("2/3", "en", style="natural"), "two thirds")
        self.assertEqual(spoken_math("3/4", "en"), "three over four")


class TestMathML(unittest.TestCase):
    def parse(self, expr: str) -> ET.Element:
        xml = to_mathml(expr)
        return ET.fromstring(xml)  # must be well-formed

    def test_root_and_alttext(self):
        root = self.parse("x^2 + 1 = 5")
        self.assertEqual(root.tag, MML + "math")
        self.assertEqual(root.attrib["alttext"], "x au carré plus un égale cinq")

    def test_structures(self):
        cases = {
            "3/4": "mfrac", "\\frac{a+b}{c}": "mfrac", "x^2": "msup", "x²": "msup", "x_1": "msub",
            "\\sqrt{x}": "msqrt", "√9": "msqrt", "\\sqrt[3]{8}": "mroot", "(a+b)": "mo", "x_1^2": "msubsup",
        }
        for expr, tag in cases.items():
            with self.subTest(expr=expr):
                root = self.parse(expr)
                self.assertTrue(list(root.iter(MML + tag)), expr)

    def test_numbers_operators_identifiers(self):
        root = self.parse("2,5 + x ≤ 7")
        self.assertEqual([e.text for e in root.iter(MML + "mn")], ["2,5", "7"])
        self.assertIn("≤", [e.text for e in root.iter(MML + "mo")])
        self.assertEqual([e.text for e in root.iter(MML + "mi")], ["x"])

    def test_minus_is_u2212(self):
        root = self.parse("5 - 3")
        self.assertIn("−", [e.text for e in root.iter(MML + "mo")])

    def test_units_and_percent(self):
        root = self.parse("AB = 5 cm")
        self.assertIn("cm", [e.text for e in root.iter(MML + "mi")])
        self.assertTrue(list(self.parse("35°").iter(MML + "mo")))

    def test_escaping(self):
        root = self.parse("x < 3")
        self.assertIn("<", [e.text for e in root.iter(MML + "mo")])
        self.assertIn("&lt;", to_mathml("x < 3"))
        self.assertNotIn('"<', to_mathml("x < 3"))

    def test_implicit_multiplication_is_explicit(self):
        xml = to_mathml("3x")
        self.assertIn("⁢", ET.fromstring(xml).itertext().__next__() + "".join(ET.fromstring(xml).itertext()))

    def test_dollar_wrapped(self):
        self.parse("$\\frac{1}{2}$")

    def test_unsupported_raises_value_error(self):
        for bad in ["", "   ", "import os", "__import__('os')", "3 4", "x = {", "\\foo{1}", "\\frac{1}", "((1)", "x ^",
                    "<script>", "\\begin{matrix}", "x" * 500, "{" * 40 + "1" + "}" * 40, "a & b"]:
            with self.subTest(bad=bad[:30]):
                with self.assertRaises(ValueError):
                    to_mathml(bad)

    def test_no_eval(self):
        # Never evaluates: a Python-looking payload is rejected, not executed.
        with self.assertRaises(ValueError):
            to_mathml("__import__('os').system('echo hacked')")


class TestProfiles(unittest.TestCase):
    def test_at_least_eight_plus_default(self):
        self.assertGreaterEqual(len(PROFILES), 9)
        self.assertIn("default", PROFILES)
        for n in ("lecture_vocale", "texte_aere", "une_etape_a_la_fois", "langage_litteral",
                  "sans_pression_temps", "contraste_zoom"):
            self.assertIn(n, PROFILES)

    def test_fields_match_the_contract(self):
        names = [f.name for f in dataclasses.fields(Profile)]
        self.assertEqual(names, ["name", "label_fr", "label_en", "needs", "max_sentence_words",
                                 "max_steps_per_reply", "forbid_figurative", "forbid_time_pressure",
                                 "spoken_math", "limit_symbols", "limit_emoji"])

    def test_frozen(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            PROFILES["default"].name = "x"  # type: ignore[misc]

    def test_no_diagnosis_anywhere(self):
        banned = re.compile(r"dys|tdah|adhd|autis|handicap|sourd|aveugle|deaf|blind|diagnos|trouble|disorder|syndrom", re.I)
        for p in PROFILES.values():
            for text in (p.name, p.label_fr, p.label_en, *p.needs):
                self.assertIsNone(banned.search(text), (p.name, text))
        for fr, en in NEEDS.values():
            self.assertIsNone(banned.search(fr + en), (fr, en))

    def test_profile_fields_hold_no_pupil_data(self):
        # A profile has no free-text field that could carry a pupil's message or a diagnosis.
        for f in dataclasses.fields(Profile):
            if f.name not in ("name", "label_fr", "label_en"):
                self.assertNotIn(f.type, ("str", str))

    def test_needs_are_in_vocabulary(self):
        for p in PROFILES.values():
            for n in p.needs:
                self.assertIn(n, NEEDS)
            if p.name != "default":
                self.assertTrue(p.needs)

    def test_coverage_of_required_needs(self):
        used = {n for p in PROFILES.values() for n in p.needs}
        for n in ("lecture_ecran", "vision_reduite", "lecture_fluente", "nombres_symboles", "attention_soutenue",
                  "langage_litteral", "texte_prioritaire", "motricite_fine"):
            self.assertIn(n, used)

    def test_default_is_neutral(self):
        d = PROFILES["default"]
        self.assertEqual((d.max_sentence_words, d.max_steps_per_reply, d.limit_emoji), (None, None, None))
        self.assertFalse(any((d.forbid_figurative, d.forbid_time_pressure, d.spoken_math, d.limit_symbols)))

    def test_unknown_profile(self):
        with self.assertRaises(ValueError):
            lint("x", "dyslexie")

    def test_combine_takes_strictest(self):
        c = combine_profiles(["texte_aere", "une_etape_a_la_fois", "lecture_vocale"])
        self.assertEqual(c.max_sentence_words, 12)
        self.assertEqual(c.max_steps_per_reply, 1)
        self.assertEqual(c.limit_emoji, 0)
        self.assertTrue(c.spoken_math and c.forbid_time_pressure)
        self.assertEqual(combine_profiles([]).name, "default")

    def test_profile_object_accepted(self):
        self.assertEqual(codes("ATTENTION", PROFILES["default"]), codes("ATTENTION", "default"))


class TestLexicons(unittest.TestCase):
    def test_sizes(self):
        lex = access._lexicons()
        self.assertGreaterEqual(len(lex["figurative"]["fr"]), 40)
        self.assertGreaterEqual(len(lex["figurative"]["en"]), 20)
        for must in ("ça roule", "c'est du gâteau", "avoir le cafard", "pas de panique", "coup de main", "dans la poche"):
            self.assertTrue(any(must in p or p in must for p in lex["figurative"]["fr"]), must)
        for must in ("vite", "rapidement", "chrono", "dépêche-toi", "en moins de"):
            self.assertIn(must, lex["time_pressure"]["fr"])
        self.assertIn("hurry", lex["time_pressure"]["en"])

    def test_curly_apostrophe_matches(self):
        self.assertIn("FIGURATIVE", codes("C’est du gâteau.", "langage_litteral"))


class TestLint(unittest.TestCase):
    def test_finding_shape(self):
        fs = lint("Pas de panique ! ATTENTION", "langage_litteral")
        self.assertTrue(fs)
        for f in fs:
            self.assertIsInstance(f, Finding)
            self.assertIn(f.severity, ("info", "warn"))
            self.assertTrue(f.message_fr and f.message_en)
            self.assertTrue(f.span is None or (isinstance(f.span, tuple) and f.span[0] < f.span[1]))

    def test_span_points_at_the_text(self):
        text = "Bravo, c'est du gâteau !"
        f = next(x for x in lint(text, "langage_litteral") if x.code == "FIGURATIVE")
        self.assertIn("gâteau", text[slice(*f.span)])

    def test_sentence_length_threshold_is_exact(self):
        ok = " ".join(["mot"] * 12) + "."
        too_long = " ".join(["mot"] * 13) + "."
        self.assertNotIn("LONG_SENTENCE", codes(ok, "une_etape_a_la_fois"))
        self.assertIn("LONG_SENTENCE", codes(too_long, "une_etape_a_la_fois"))

    def test_decimal_point_does_not_split_sentences(self):
        self.assertNotIn("LONG_SENTENCE", codes("Calcule 3.5 puis 4.5 puis 5.5 puis 6.5 maintenant.", "une_etape_a_la_fois"))

    def test_default_profile_only_universal_checks(self):
        got = codes("1. a\n2. b\n3. c\nPas de panique, dépêche-toi → vite 😀😀😀😀", "default")
        self.assertEqual(got, set())

    def test_negated_time_pressure(self):
        self.assertNotIn("TIME_PRESSURE", codes("Sans te presser, ne va pas trop vite.", "sans_pression_temps"))
        self.assertIn("TIME_PRESSURE", codes("Va vite.", "sans_pression_temps"))

    def test_vitesse_and_chronologie_are_not_flagged(self):
        self.assertNotIn("TIME_PRESSURE", codes("La vitesse et la chronologie.", "sans_pression_temps"))

    def test_all_caps_exceptions(self):
        self.assertNotIn("CAPS_SHOUTING", codes("Dans ABCD et EFGH, le PGCD est utile.", "default"))
        self.assertIn("CAPS_SHOUTING", codes("DANGER", "default"))

    def test_emoji_variants_counted_once(self):
        self.assertEqual(sum(f.code == "EMOJI_EXCESS" for f in lint("👍🏽 ❤️ 👨‍👩‍👧", "lecture_vocale")), 1)
        self.assertNotIn("EMOJI_EXCESS", codes("Bravo ✓", "default"))

    def test_english_lexicon_by_lang(self):
        self.assertIn("FIGURATIVE", codes("It is a piece of cake.", "langage_litteral", "en"))
        self.assertNotIn("FIGURATIVE", codes("It is a piece of cake.", "langage_litteral", "fr"))

    def test_bad_language(self):
        with self.assertRaises(ValueError):
            lint("x", "default", "de")

    def test_empty_reply(self):
        for p in PROFILES:
            self.assertEqual(lint("", p), [])

    def test_ascii_arrow_vs_inequality(self):
        self.assertNotIn("SYMBOL_UNEXPLAINED", codes("Si x <= 3 et y >= 2 alors x<-3 est faux.", "lecture_vocale"))


class TestCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = [json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_size_and_schema(self):
        self.assertGreaterEqual(len(self.cases), 60)
        keys = {"id", "profile", "lang", "input", "expect_codes", "expect_absent_codes", "spoken_expected", "note"}
        ids = set()
        for c in self.cases:
            self.assertEqual(set(c), keys, c.get("id"))
            self.assertNotIn(c["id"], ids)
            ids.add(c["id"])
            self.assertIn(c["profile"], PROFILES)
            self.assertIn(c["lang"], ("fr", "en"))
            self.assertTrue(set(c["expect_codes"]).isdisjoint(c["expect_absent_codes"]))

    def test_all_cases(self):
        for c in self.cases:
            with self.subTest(case=c["id"]):
                if c["spoken_expected"] is not None:
                    self.assertEqual(spoken_math(c["input"], c["lang"]), c["spoken_expected"])
                got = codes(c["input"], c["profile"], c["lang"])
                for code in c["expect_codes"]:
                    self.assertIn(code, got)
                for code in c["expect_absent_codes"]:
                    self.assertNotIn(code, got)

    def test_corpus_covers_every_lint_code(self):
        covered = {code for c in self.cases for code in c["expect_codes"]}
        for code in ("LONG_SENTENCE", "TOO_MANY_STEPS", "TOO_MANY_QUESTIONS", "FIGURATIVE", "TIME_PRESSURE",
                     "SYMBOL_UNEXPLAINED", "ASCII_ART", "TABLE", "EMOJI_EXCESS", "COLOR_ONLY", "VISUAL_DEIXIS",
                     "AUDIO_ONLY_CUE", "CAPS_SHOUTING", "LONG_PARAGRAPH", "RAW_LATEX", "TYPING_HEAVY"):
            self.assertIn(code, covered)

    def test_corpus_has_both_languages(self):
        self.assertEqual({c["lang"] for c in self.cases}, {"fr", "en"})


def _numbers(text: str) -> Counter:
    return Counter(re.findall(r"\d+", text))


class TestAdapt(unittest.TestCase):
    LONG = ("Pour résoudre cette équation, il faut d'abord isoler x dans le membre de gauche, puis diviser les deux "
            "membres par 3, et enfin vérifier le résultat obtenu avec la valeur 12.")

    def test_never_changes_or_adds_numbers(self):
        samples = [self.LONG, "Calcule 3,5 + 4 😀😀😀. 1. a 2. b 3. c", "Résous $\\frac{3}{4} + 2$, car 7 > 5; donc oui.",
                   "Étape 1 : isole x. Étape 2 : divise par 3. Étape 3 : vérifie 15.", ""]
        for s in samples:
            for p in PROFILES:
                with self.subTest(p=p, s=s[:25]):
                    out = adapt(s, p)
                    self.assertEqual(_numbers(out.text), _numbers(s))

    def test_idempotent(self):
        for p in PROFILES:
            once = adapt(self.LONG + " 😀😀😀", p).text
            self.assertEqual(adapt(once, p).text, once, p)

    def test_long_sentence_is_split_at_conjunction(self):
        out = adapt(self.LONG, "une_etape_a_la_fois")
        self.assertIn("ADAPT_SENTENCE_SPLIT", {f.code for f in out.findings})
        self.assertGreater(out.text.count("."), self.LONG.count("."))
        self.assertNotIn(", puis", out.text)
        self.assertIn("Puis ", out.text)
        for sent in re.split(r"(?<=[.!?])\s+", out.text):
            self.assertLessEqual(len(sent.split()), 12 + 8)  # shorter than original (30+ words)

    def test_no_split_inside_parentheses_or_enumeration(self):
        s = "Tu peux utiliser les nombres (2, et 3) pour calculer la somme complète de tous les termes de la liste donnée."
        self.assertEqual(adapt(s, "une_etape_a_la_fois").text, s)
        s2 = "Prends le crayon, la règle, et le compas pour tracer la figure demandée sur la feuille blanche devant toi."
        self.assertEqual(adapt(s2, "une_etape_a_la_fois").text, s2)

    def test_emoji_limit_applied(self):
        out = adapt("Bravo 😀😀😀 !", "texte_aere")
        self.assertEqual(out.text.count("😀"), 2)
        self.assertEqual(adapt("Bravo 😀😀 !", "lecture_vocale").text, "Bravo !")
        self.assertIn("ADAPT_EMOJI_REMOVED", {f.code for f in adapt("Bravo 😀 !", "lecture_vocale").findings})

    def test_steps_on_their_own_line(self):
        out = adapt("Voici le plan. 1. Isole x. 2. Divise par 3.", "texte_aere")
        self.assertIn("\n1. Isole x.", out.text)
        self.assertIn("\n2. Divise par 3.", out.text)
        self.assertEqual(adapt("x = 2.5 puis 3.", "texte_aere").text, "x = 2.5 puis 3.")

    def test_spoken_only_for_speech_profiles(self):
        self.assertIsNone(adapt("x = 5", "texte_aere").spoken)
        self.assertEqual(adapt("x = 5", "lecture_vocale").spoken, "x égale cinq.")
        self.assertEqual(adapt("Donc $x = 5$ 😀", "nombres_clairs").spoken, "Donc x égale cinq.")
        self.assertEqual(adapt("x = 5", "lecture_vocale", "en").spoken, "x equals five.")

    def test_mathml_extracted_in_order(self):
        out = adapt("On a $\\frac{1}{2}$ puis $x^2$.", "lecture_vocale")
        self.assertEqual(len(out.mathml), 2)
        for m in out.mathml:
            ET.fromstring(m)
        self.assertIn("mfrac", out.mathml[0])
        self.assertIn("msup", out.mathml[1])
        self.assertEqual(adapt("On a $\\foo{1}$.", "lecture_vocale").mathml, [])
        self.assertIn("ADAPT_MATHML_SKIPPED", {f.code for f in adapt("On a $\\foo{1}$.", "lecture_vocale").findings})

    def test_equation_line_gets_mathml(self):
        out = adapt("Donc :\n2x + 3 = 7\nVoilà.", "lecture_vocale")
        self.assertEqual(len(out.mathml), 1)

    def test_remaining_problems_still_reported(self):
        out = adapt("Pas de panique, c'est du gâteau.", "langage_litteral")
        self.assertIn("FIGURATIVE", {f.code for f in out.findings})
        self.assertEqual(out.text, "Pas de panique, c'est du gâteau.")  # adapt does not rewrite idioms

    def test_default_is_identity(self):
        s = "Voici 3 + 4 😀😀😀. 1. a 2. b"
        out = adapt(s, "default")
        self.assertEqual(out.text, s)
        self.assertIsNone(out.spoken)
        self.assertEqual(out.mathml, [])

    def test_hint_not_answer_text_is_kept_verbatim(self):
        hint = "Indice : isole x puis relis la consigne."
        for p in PROFILES:
            self.assertIn("Indice", adapt(hint, p).text)

    def test_mixed_language_en(self):
        out = adapt("First subtract three from both sides, then divide the result by two, and finally check your answer carefully.", "une_etape_a_la_fois", "en")
        self.assertIn("Then ", out.text)


class TestAddendumAndExplain(unittest.TestCase):
    def test_default_is_empty(self):
        self.assertEqual(profile_prompt_addendum("default"), "")
        self.assertEqual(profile_prompt_addendum("default", "en"), "")

    def test_concrete_constraints_present(self):
        a = profile_prompt_addendum("une_etape_a_la_fois")
        self.assertIn("12 mots", a)
        self.assertIn("Une seule étape", a)
        self.assertIn("vite", a)
        b = profile_prompt_addendum("langage_litteral")
        self.assertIn("expression imagée", b)
        self.assertIn("Pas d'emoji", b)
        c = profile_prompt_addendum("lecture_vocale")
        self.assertIn("voix haute", c)
        self.assertIn("20 mots", c)

    def test_every_addendum_keeps_pedagogical_contract_and_no_diagnosis_prompting(self):
        for name in PROFILES:
            if name == "default":
                continue
            for lang, needle in (("fr", "jamais la réponse finale"), ("en", "never the final answer")):
                a = profile_prompt_addendum(name, lang)
                self.assertIn(needle, a)
                self.assertRegex(a, r"(?i)jamais un diagnostic|never a diagnosis")

    def test_english(self):
        a = profile_prompt_addendum("une_etape_a_la_fois", "en")
        self.assertIn("12 words", a)
        self.assertIn("One step", a)

    def test_addendum_is_deterministic_and_short(self):
        for name in PROFILES:
            self.assertEqual(profile_prompt_addendum(name), profile_prompt_addendum(name))
            self.assertLess(len(profile_prompt_addendum(name)), 1500)

    def test_explain(self):
        for name, p in PROFILES.items():
            fr = explain_profile(name)
            en = explain_profile(name, "en")
            self.assertIn("pas un diagnostic" if name != "default" else "Aucune adaptation", fr)
            self.assertIn("not a diagnosis" if name != "default" else "No adaptation", en)
        self.assertIn("12 mots", explain_profile("une_etape_a_la_fois"))
        self.assertIn("Une seule étape", explain_profile("une_etape_a_la_fois"))


if __name__ == "__main__":
    unittest.main()
