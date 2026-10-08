import unittest

from emma_college.harness import Harness

EX = {"statement": "Résous 3x + 5 = 20.", "answer": "x=5"}


class H(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def test_leak_is_masked(self):
        r = self.h.check("donne la réponse", "La solution est x = 5.", EX)
        self.assertIn("block", r.verdicts)
        self.assertNotIn("5", r.reply.replace("〔", ""))

    def test_hint_passes(self):
        r = self.h.check("aide-moi", "Soustrais 5 des deux côtés : que devient l'équation ?", EX)
        self.assertEqual(r.verdicts, [])

    def test_correct_attempt_is_not_blocked(self):
        r = self.h.check("je trouve x=5", "Oui, x = 5 : tu peux vérifier en remplaçant.", EX, "x=5")
        self.assertNotIn("block", r.verdicts)

    def test_false_praise_on_wrong_attempt(self):
        r = self.h.check("je trouve x=4", "Bravo, c'est exact !", EX, "x=4")
        self.assertIn("false_praise", r.verdicts)
        r = self.h.check("je trouve x=4", "Pas tout à fait : vérifie en remplaçant x par 4.", EX, "x=4")
        self.assertNotIn("false_praise", r.verdicts)

    def test_pii_and_distress(self):
        self.assertIn("pii_redact", self.h.check("x", "Écris à a@b.fr", EX).verdicts)
        self.assertTrue(self.h.pre("je veux me tuer").block_model_call)
        self.assertIn("pii_redact", self.h.pre("mon mail est a@b.fr").verdicts)

    def test_guess_without_exercise(self):
        r = self.h.check("combien fait 7 x 8 ?", "Ça fait 56.")
        self.assertIn("block", r.verdicts)


if __name__ == "__main__":
    unittest.main()


class TestHostileInput(unittest.TestCase):
    def test_huge_reply_is_bounded(self):
        import time
        from emma_college.harness import Harness
        t = time.time()
        r = Harness().check("a", "9" * 200000, {"statement": "", "answer": "x=5"})
        self.assertLess(time.time() - t, 3)
        self.assertIn("truncated", r.verdicts)
