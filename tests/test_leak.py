import unittest

from emma_college import leak as L


def leaks(ans, reply, stmt=""):
    return [x.text.strip() for x in L.find_leaks(reply, [L.parse_answer(ans)], stmt)]


class Leaks(unittest.TestCase):
    def yes(self, ans, reply, stmt=""):
        self.assertTrue(leaks(ans, reply, stmt), (ans, reply))

    def no(self, ans, reply, stmt=""):
        self.assertEqual(leaks(ans, reply, stmt), [], (ans, reply))

    def test_integers_and_forms(self):
        for r in ["Le résultat est 5.", "Donc +5 !", "Ça fait cinq", "Réponse : cinq",
                  "**5**", "5 est la solution", "On a x = 5", "Alors 5,0", "= 10/2"]:
            self.yes("5", r + (" " if r[-1] != " " else ""))

    def test_good_hints_pass(self):
        self.no("5", "Ajoute 12 puis retire 7.", "Calcule (-7) + 12.")
        self.no("5", "1. Lis l'énoncé\n2. Choisis la méthode")
        self.no("5", "En 4e, tu as vu les relatifs.")
        self.no("5", "Pour la 5e étape, relis.")

    def test_result_position_not_exempted_by_statement(self):
        # "10" is both a given of the statement and the answer: stated in
        # result position it is an announcement, not a quote (stat-01).
        self.yes("10", "La moyenne est 10.", "Calcule la moyenne de 8, 12 et 10.")
        self.yes("10", "(8 + 12 + 10) / 3 = 10", "Calcule la moyenne de 8, 12 et 10.")
        # same value mentioned mid-sentence (not in result position): given
        # data restated in a hint, not a leak
        self.no("10", "Regarde le 10 de l'énoncé : c'est l'un des trois nombres.",
                "Calcule la moyenne de 8, 12 et 10.")

    def test_fractions(self):
        for r in ["Tu obtiens 6/8.", "soit 0,75", "c'est 75 %", "\\frac{3}{4}", "trois quarts",
                  "C'est égal à 3/4"]:
            self.yes("3/4", r + " ")
        self.no("3/4", "Simplifie 6/8 en divisant par 2.", "Simplifie 6/8.")
        self.no("3/4", "Mets au même dénominateur : 1/2 et 1/4.")

    def test_division_instruction_is_not_a_leak(self):
        self.no("5", "Divise 15 par 3 ?", "Résous 3x = 15.")
        self.no("5", "Tu peux écrire 15/3 si tu veux.", "Résous 3x = 15.")

    def test_radicals(self):
        self.yes("4*sqrt(2)", "Cela vaut 4√2.")
        self.yes("4*sqrt(2)", "Donc \\sqrt{32}.")
        self.yes("4*sqrt(2)", "environ 5,66")
        self.no("4*sqrt(2)", "Écris 32 = 16 × 2.", "Simplifie √32.")

    def test_equations(self):
        self.yes("x=5", "Alors x = 5.", "Résous 3x + 5 = 20.")
        self.no("x=5", "3x = 15, tu divises par 3 ?", "Résous 3x + 5 = 20.")
        self.no("x=3", "Divise par 3 : que vaut 3x ?", "Résous 3x + 5 = 14.")
        self.yes("x=3", "x = 3", "Résous 3x + 5 = 14.")
        self.yes("x<=3", "On trouve x ≤ 3.")

    def test_polynomials(self):
        self.yes("x^2-9", "Ça donne (x-3)(x+3).", "Factorise x² - 9.")
        self.no("x^2-9", "Rappel : a² - b² = (a-b)(a+b).", "Factorise x² - 9.")
        self.no("x^2-9", "Reprends x² - 9 et cherche a et b.", "Factorise x² - 9.")

    def test_percent(self):
        self.yes("20%", "Cela fait 20 %.")
        self.yes("20%", "soit 0,2")

    def test_measures(self):
        self.yes("13 cm", "AC = 13 cm.", "Calcule AC.")
        self.no("13 cm", "Calcule 12² + 5² d'abord.", "Calcule AC.")

    def test_scientific(self):
        self.yes("5*10^3", "On obtient 5 × 10³.")
        self.yes("5*10^3", "donc 5000 ")

    def test_masking(self):
        r = "La réponse est 5."
        out = L.mask(r, L.find_leaks(r, [L.parse_answer("5")]))
        self.assertNotIn("5", out)

    def test_guess(self):
        v = lambda s: [a.scalars for a in L.guess_answers(s)]
        self.assertEqual(v("combien fait 7 x 8 ?")[0][0], 56)
        self.assertEqual(v("résous 3x+5=20")[0][0], 5)
        self.assertEqual(v("calcule 3/4 + 1/2")[0][0].numerator, 5)
        self.assertEqual(v("bonjour"), [])


if __name__ == "__main__":
    unittest.main()


class TestLatexForms(unittest.TestCase):
    def test_latex_times_and_braced_exponent(self):
        from emma_college import leak
        a = leak.parse_answer("300000")
        self.assertTrue(leak.find_leaks(r"La réponse est 3 \times 10^5", [a], ""))
        b = leak.parse_answer("x^2-9")
        self.assertTrue(leak.find_leaks("On a x^{2} - 9", [b], ""))


class KnownGapsExpectedFailures(unittest.TestCase):
    """Known missed leaks, documented in agent/reports/2026-10-08.md and
    ESCALADÉ to the human in agent/answers/2026-10-08.md.

    Each test states what the detector SHOULD catch once a human approves
    the corresponding extension (bare number-word replies / `π` parsing /
    English number words). They are marked ``expectedFailure``: the suite
    stays green while the gap is open, and each one turns into a plain
    pass the day the fix lands. Do NOT remove the decorator to "fix" a
    gap without the written decision it was escalated under."""

    @unittest.expectedFailure
    def test_gap_pct01_worded_answer(self):
        # corpus pct-01, form "worded": "Soixante euros." (answer 60).
        # A bare number word at sentence start, with no result marker
        # before it, is not caught by the word path.
        self.assertTrue(leaks("60", "Soixante euros."))

    @unittest.expectedFailure
    def test_gap_vol01_pi_answer_unparsed(self):
        # corpus vol-01: `parse_answer("36π")` returns an empty Answer
        # (mathcore does not accept the unicode π), so "V = 36π cm³."
        # has no target scalar and is never flagged.
        self.assertTrue(L.parse_answer("36π").scalars)
        self.assertTrue(leaks("36π", "V = 36π cm³."))

    @unittest.expectedFailure
    def test_gap_en_eq01_english_number_word(self):
        # corpus en-eq-01, form "worded": "x is five." (answer x=5).
        # English number words are not in the word lexicon at all.
        self.assertTrue(leaks("x=5", "x is five."))

    def test_gap_boundary_digit_forms_still_detected(self):
        # Guards the exact boundary of the two word-form gaps: the
        # digit form of the same corpus replies IS caught today. These
        # must keep passing so a fix to the word path cannot regress
        # the digit path.
        self.assertTrue(leaks("60", "Le prix soldé est 60 €."))
        self.assertTrue(leaks("x=5", "The solution is x = 5."))
