import unittest
from fractions import Fraction as F

from emma_college import mathcore as mc
from emma_college.mathcore import Rad, Unsupported


class Eval(unittest.TestCase):
    def sc(self, s):
        return mc.evaluate_scalar(s)

    def test_arithmetic(self):
        for s, v in [("7*8", 56), ("7 x 8", None), ("(-7)+12", 5), ("12 - 20", -8),
                     ("2^3", 8), ("2²", 4), ("10^(-2)", F(1, 100)), ("−3 × −4", 12),
                     ("1 000 + 1", 1001), ("0,5 + 0,25", F(3, 4)), ("12 ÷ 4", 3),
                     ("3/4 + 1/2", F(5, 4)), ("(1/2)*(2/3)", F(1, 3)), ("½ + ¼", F(3, 4)),
                     ("50 %", F(1, 2)), ("2(3+4)", 14), ("-(-2)", 2)]:
            if v is None:
                continue
            self.assertEqual(self.sc(s), F(v), s)

    def test_radicals(self):
        self.assertEqual(self.sc("sqrt(32)"), Rad(F(4), 2))
        self.assertEqual(self.sc("√32"), Rad(F(4), 2))
        self.assertEqual(self.sc("\\sqrt{50}"), Rad(F(5), 2))
        self.assertEqual(self.sc("sqrt(16)"), F(4))
        self.assertEqual(self.sc("sqrt(9/4)"), F(3, 2))
        self.assertEqual(self.sc("2*sqrt(3)*3*sqrt(3)"), F(18))
        self.assertEqual(self.sc("sqrt(2)*sqrt(8)"), F(4))
        self.assertEqual(self.sc("sqrt(2)+sqrt(2)"), Rad(F(2), 2))
        self.assertEqual(self.sc("1/sqrt(2)"), Rad(F(1, 2), 2))

    def test_latex_and_typography(self):
        self.assertEqual(self.sc("\\frac{3}{4}"), F(3, 4))
        self.assertEqual(self.sc("\\dfrac{6}{8}"), F(3, 4))
        self.assertEqual(self.sc("3− 5"), F(-2))
        self.assertEqual(self.sc("2 500"), F(2500))

    def test_polynomials(self):
        a = mc.evaluate("(x-3)(x+3)", allow_var=True)
        b = mc.evaluate("x^2-9", allow_var=True)
        self.assertEqual(a, b)
        self.assertEqual(mc.evaluate("(x+1)^2", True), mc.evaluate("x²+2x+1", True))
        self.assertNotEqual(mc.evaluate("(x+1)^2", True), mc.evaluate("x²+1", True))
        self.assertEqual(mc.evaluate("2(x+3)", True), mc.evaluate("2x+6", True))

    def test_relations(self):
        self.assertEqual(mc.solve_relation("3x + 5 = 20"), ("=", F(5)))
        self.assertEqual(mc.solve_relation("2x - 3 = x + 4"), ("=", F(7)))
        self.assertEqual(mc.solve_relation("-2x <= 6"), (">=", F(-3)))
        self.assertEqual(mc.solve_relation("x/2 + 1 = 4"), ("=", F(6)))
        self.assertEqual(mc.solve_relation("x + 1 = x + 1")[0], "identity")
        self.assertEqual(mc.solve_relation("x + 1 = x + 2")[0], "impossible")
        self.assertEqual(mc.solve_relation("3x > 9"), (">", F(3)))

    def test_out_of_scope(self):
        for s in ["x^2 = 9", "foo", "1/0", "2^x"]:
            with self.assertRaises(Unsupported):
                if "=" in s:
                    mc.solve_relation(s)
                else:
                    mc.evaluate_scalar(s)

    def test_no_eval_injection(self):
        for s in ["__import__('os')", "1; import os", "().__class__"]:
            with self.assertRaises(Unsupported):
                mc.evaluate_scalar(s)


if __name__ == "__main__":
    unittest.main()
