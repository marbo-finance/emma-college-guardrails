"""Short answers written in letters (FR/EN) and English number words."""
import time
import unittest
from fractions import Fraction

from emma_college.leak import find_leaks, parse_answer
from emma_college.words import find_number_words_en


def leaks(reply, answer, statement=""):
    return find_leaks(reply, [parse_answer(answer)], statement)


class EnglishWords(unittest.TestCase):
    def val(self, text):
        return [v for _, _, v in find_number_words_en(text)]

    def test_units_and_teens(self):
        self.assertEqual(self.val("five"), [Fraction(5)])
        self.assertEqual(self.val("Nineteen"), [Fraction(19)])

    def test_hyphen_compound(self):
        self.assertEqual(self.val("forty-two"), [Fraction(42)])

    def test_hundreds_and_thousands(self):
        self.assertEqual(self.val("two hundred and five"), [Fraction(205)])
        self.assertEqual(self.val("three thousand four hundred"), [Fraction(3400)])

    def test_plain_words_ignored(self):
        self.assertEqual(self.val("and the answer"), [])


class WordedLeaks(unittest.TestCase):
    def test_fr_amount_with_unit(self):
        self.assertTrue(leaks("Soixante euros.", "60"))

    def test_fr_capital_and_hyphen(self):
        self.assertTrue(leaks("Quarante-deux.", "42"))

    def test_en_equation_answer(self):
        self.assertTrue(leaks("x is five.", "x=5"))

    def test_en_answer_is(self):
        self.assertTrue(leaks("The answer is twelve.", "12"))

    def test_en_compound(self):
        self.assertTrue(leaks("It is forty-two.", "42"))

    def test_other_value_not_flagged(self):
        self.assertFalse(leaks("Soixante euros.", "61"))
        self.assertFalse(leaks("x is five.", "x=6"))

    def test_imperative_hint_not_flagged(self):
        self.assertFalse(leaks("Ajoute soixante euros au prix.", "60"))
        self.assertFalse(leaks("Ajoute soixante euros.", "60"))

    def test_hint_quoting_statement_not_flagged(self):
        self.assertFalse(leaks("Soixante euros, c'est le prix de départ.", "60",
                               "Un article à soixante euros est soldé."))

    def test_en_hint_not_flagged(self):
        self.assertFalse(leaks("Add five to both sides, then divide.", "5"))
        self.assertFalse(leaks("Subtract five from both sides first.", "5"))

    def test_digits_in_sentence_not_short_answer(self):
        self.assertFalse(leaks("Calcule 3x puis ajoute cinq.", "5"))

    def test_performance(self):
        text = ("three " * 2000) + "x is five." + (" so" * 2000)
        t = time.time()
        leaks(text, "x=5")
        self.assertLess(time.time() - t, 1.0)


if __name__ == "__main__":
    unittest.main()


class ReviewRegressions(unittest.TestCase):
    def test_and_does_not_merge_numbers(self):
        self.assertEqual([v for _, _, v in find_number_words_en("two and three")],
                         [Fraction(2), Fraction(3)])
        self.assertFalse(leaks("The solutions are two and three.", "5"))

    def test_span_has_no_trailing_and(self):
        (s, e, _), = find_number_words_en("x is five and you multiply.")
        self.assertEqual("x is five and you multiply."[s:e], "five")

    def test_clause_not_short_answer(self):
        self.assertFalse(leaks("Ici, deux étapes suffisent.", "2"))
        self.assertFalse(leaks("A two step equation.", "2"))

    def test_accented_lead_in(self):
        self.assertTrue(leaks("La réponse vaut soixante.", "60"))
