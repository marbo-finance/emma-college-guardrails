import unittest

from emma_college import curriculum as C
from emma_college.harness import Harness


class Classify(unittest.TestCase):
    def test_pythagore_is_4e(self):
        i = C.classify("Dans un triangle rectangle en A, AB=3 et AC=4. Calcule BC (Pythagore).")
        self.assertIn("pyth", [t.code for t in i.themes])
        self.assertEqual(i.level, "4e")

    def test_rectangle_en_variant_is_4e(self):
        i = C.classify("Triangle ABC rectangle en A, AB = 6 cm et AC = 8 cm. Calcule BC.")
        self.assertEqual(i.level, "4e")

    def test_thales_trigo_are_3e(self):
        i = C.classify("Avec le théorème de Thalès puis le cosinus de l'angle, calcule la longueur.")
        self.assertEqual({t.code for t in i.themes} & {"thal", "trig"}, {"thal", "trig"})
        self.assertEqual(i.level, "3e")

    def test_accents_and_case_folded(self):
        self.assertTrue(C.classify("DÉVELOPPE (x+2)(x-5) : ÉQUATION").themes)

    def test_equation_is_cycle4(self):
        i = C.classify("Résous l'équation 3x + 5 = 20.")
        self.assertEqual(i.level, "cycle4")

    def test_out_of_scope_flagged_once(self):
        i = C.classify("Calcule la dérivée, puis la dérivée seconde et le logarithme.")
        self.assertEqual([a for a, b in i.out_of_scope], ["dérivée", "logarithme"])

    def test_unknown_text_stays_silent(self):
        i = C.classify("Bonjour, comment ça va ?")
        self.assertEqual((i.themes, i.level, i.out_of_scope), ([], "", []))

    def test_as_dict_en(self):
        d = C.classify("Use the Pythagorean theorem on the hypotenuse.").as_dict("en")
        self.assertIn("Pythagorean theorem", d["themes"])


class Prompt(unittest.TestCase):
    def test_addendum_in_system_prompt(self):
        for lang in ("fr", "en"):
            sp = Harness(lang=lang).system_prompt()
            frag = "Cadre du programme" if lang == "fr" else "Curriculum frame"
            self.assertIn(frag, sp)

    def test_addendum_mentions_lycee_ban(self):
        self.assertIn("dérivées", C.prompt_addendum("fr"))
        self.assertIn("derivatives", C.prompt_addendum("en"))


if __name__ == "__main__":
    unittest.main()
