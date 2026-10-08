"""Exact arithmetic for the cycle-4 (4e/3e) French maths programme.

Stdlib only. Everything is exact (``fractions.Fraction``) unless a value is
genuinely irrational, in which case it is kept as ``coef * sqrt(n)`` (``Rad``)
or, as a last resort, an ``Approx`` float.

What it can do (and is tested for):
  * decimals with a comma, unicode minus, thousands separators
  * + - x / : ^ and parentheses, implicit multiplication, superscripts
  * fractions, percentages, scientific notation
  * square roots (simplified: sqrt(32) == 4*sqrt(2))
  * one-variable polynomials (develop / factorise equivalence)
  * first-degree equations and inequalities in one unknown

What it deliberately does NOT do: calculus, systems, quadratic solving,
anything needing a CAS. When an input is out of scope it raises
``Unsupported`` and the caller falls back to weaker heuristics. It never
calls ``eval``.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Optional, Union


class Unsupported(ValueError):
    """The expression is outside what this module handles exactly."""


# ---------------------------------------------------------------------------
# value types
# ---------------------------------------------------------------------------

def _squarefree(n: int) -> tuple[int, int]:
    """Return (k, m) with n == k*k*m and m squarefree."""
    k, m, p = 1, n, 2
    while p * p <= m:
        while m % (p * p) == 0:
            m //= p * p
            k *= p
        p += 1
    return k, m


@dataclass(frozen=True)
class Rad:
    """coef * sqrt(n), n squarefree and > 1."""
    coef: Fraction
    n: int

    def __float__(self) -> float:
        return float(self.coef) * math.sqrt(self.n)


@dataclass(frozen=True)
class Approx:
    value: float

    def __float__(self) -> float:
        return self.value


def sqrt_exact(q: Fraction) -> Union[Fraction, Rad]:
    if q < 0:
        raise Unsupported("sqrt of a negative number")
    if q == 0:
        return Fraction(0)
    num_k, num_m = _squarefree(q.numerator)
    den_k, den_m = _squarefree(q.denominator)
    # sqrt(a/b) = sqrt(a*b)/b
    k, m = _squarefree(q.numerator * q.denominator)
    coef = Fraction(k, q.denominator)
    if m == 1:
        return coef
    return Rad(coef, m)


Scalar = Union[Fraction, Rad, Approx]


def to_float(v: Scalar) -> float:
    return float(v)


def scalar_eq(a: Scalar, b: Scalar, tol: float = 1e-9) -> bool:
    if isinstance(a, Fraction) and isinstance(b, Fraction):
        return a == b
    if isinstance(a, Rad) and isinstance(b, Rad):
        return a == b
    if isinstance(a, Approx) or isinstance(b, Approx):
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)))
    return False


# ---------------------------------------------------------------------------
# one-variable polynomial with Fraction coefficients
# ---------------------------------------------------------------------------

class Poly:
    """Polynomial in one unknown. ``terms`` maps exponent -> coefficient."""
    __slots__ = ("terms", "var")

    def __init__(self, terms: Optional[dict] = None, var: Optional[str] = None):
        self.terms = {e: c for e, c in (terms or {}).items() if c != 0}
        self.var = var

    @staticmethod
    def const(c) -> "Poly":
        return Poly({0: Fraction(c)})

    @staticmethod
    def x(var: str) -> "Poly":
        return Poly({1: Fraction(1)}, var)

    @property
    def degree(self) -> int:
        return max(self.terms) if self.terms else 0

    def is_const(self) -> bool:
        return all(e == 0 for e in self.terms)

    def const_value(self) -> Fraction:
        return self.terms.get(0, Fraction(0))

    def _merge_var(self, other: "Poly") -> Optional[str]:
        if self.var and other.var and self.var != other.var:
            raise Unsupported("several unknowns")
        return self.var or other.var

    def __add__(self, o: "Poly") -> "Poly":
        t = dict(self.terms)
        for e, c in o.terms.items():
            t[e] = t.get(e, Fraction(0)) + c
        return Poly(t, self._merge_var(o))

    def __neg__(self) -> "Poly":
        return Poly({e: -c for e, c in self.terms.items()}, self.var)

    def __sub__(self, o: "Poly") -> "Poly":
        return self + (-o)

    def __mul__(self, o: "Poly") -> "Poly":
        t: dict = {}
        for e1, c1 in self.terms.items():
            for e2, c2 in o.terms.items():
                t[e1 + e2] = t.get(e1 + e2, Fraction(0)) + c1 * c2
        if sum(max(abs(e), 1) for e in t) > 400:
            raise Unsupported("degree too large")
        return Poly(t, self._merge_var(o))

    def __pow__(self, n: int) -> "Poly":
        if n < 0 or n > 12:
            raise Unsupported("exponent out of range")
        r = Poly.const(1)
        for _ in range(n):
            r = r * self
        return r

    def div_const(self, c: Fraction) -> "Poly":
        if c == 0:
            raise Unsupported("division by zero")
        return Poly({e: v / c for e, v in self.terms.items()}, self.var)

    def __eq__(self, o) -> bool:
        return isinstance(o, Poly) and self.terms == o.terms

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.terms.items())))

    def __repr__(self) -> str:  # pragma: no cover
        return f"Poly({self.terms})"


Value = Union[Poly, Rad, Approx]


# ---------------------------------------------------------------------------
# lexer
# ---------------------------------------------------------------------------

_SUP = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5",
        "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁻": "-"}
_VULGAR = {"½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4",
           "⅕": "1/5", "⅖": "2/5", "⅗": "3/5", "⅘": "4/5", "⅙": "1/6",
           "⅚": "5/6", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8"}
_MINUS = "\u2212\u2013\u2012\u2010\u2011"  # unicode minus / dashes
_SPACES = "\u00a0\u202f\u2009\u2002\u2003"


def normalize_math(s: str) -> str:
    """Canonicalise typography (not meaning): minus signs, multiplication,
    division, spaces, superscripts, vulgar fractions, LaTeX wrappers."""
    out = s
    out = re.sub(r"\\(?:dfrac|tfrac|frac)\s*\{([^{}]*)\}\s*\{([^{}]*)\}",
                 r"((\1)/(\2))", out)
    out = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"sqrt(\1)", out)
    out = re.sub(r"\\sqrt\s*(\d+)", r"sqrt(\1)", out)
    out = out.replace("\\left", "").replace("\\right", "")
    out = out.replace("\\times", "*").replace("\\cdot", "*").replace("\\div", "/")
    out = out.replace("\\leq", "<=").replace("\\le", "<=").replace("\\geq", ">=")
    out = out.replace("\\ge", ">=").replace("\\pi", "pi")
    out = out.replace("$", "").replace("\\(", "").replace("\\)", "")
    out = out.replace("\\,", "").replace("\\ ", " ").replace("\\%", "%")
    out = out.replace("{", "(").replace("}", ")")
    for ch in _MINUS:
        out = out.replace(ch, "-")
    for ch in _SPACES:
        out = out.replace(ch, " ")
    for k, v in _VULGAR.items():
        out = out.replace(k, f"({v})")
    out = re.sub("[⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+",
                 lambda m: "^(" + "".join(_SUP[c] for c in m.group()) + ")", out)
    out = out.replace("√", "sqrt").replace("×", "*").replace("·", "*")
    out = out.replace("÷", "/").replace("⁄", "/").replace("∕", "/")
    out = out.replace("≤", "<=").replace("≥", ">=").replace("≠", "!=")
    out = out.replace("−", "-")
    out = re.sub(r"(?<=\d) +(?=\d{3}(?!\d))", "", out)  # thousands: 1 000
    out = re.sub(r"(?<=\d),(?=\d)", ".", out)            # decimal comma
    out = re.sub(r"(?<=\d)(?:\s*)\*\s*10\^", "*10^", out)
    return out


_TOKEN_RE = re.compile(
    r"\s*(?:(?P<num>\d+(?:\.\d+)?)|(?P<sqrt>sqrt)|(?P<pi>pi)"
    r"|(?P<var>[a-zA-Z])|(?P<op><=|>=|!=|[-+*/:^()=<>%]))")


def _lex(s: str) -> list[tuple[str, str]]:
    toks: list[tuple[str, str]] = []
    i = 0
    s = s.strip()
    while i < len(s):
        m = _TOKEN_RE.match(s, i)
        if not m or m.end() == i:
            raise Unsupported(f"unexpected character {s[i:i+1]!r}")
        i = m.end()
        kind = m.lastgroup
        toks.append((kind, m.group(kind)))
    return toks


# ---------------------------------------------------------------------------
# parser / evaluator (recursive descent)
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, toks, allow_var: bool):
        self.t = toks
        self.i = 0
        self.allow_var = allow_var

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def eat(self, kind=None, val=None):
        k, v = self.peek()
        if k is None or (kind and k != kind) or (val and v != val):
            raise Unsupported("syntax")
        self.i += 1
        return k, v

    # expr := term (('+'|'-') term)*
    def expr(self) -> Value:
        v = self.term()
        while True:
            k, op = self.peek()
            if k == "op" and op in "+-" and len(op) == 1:
                self.i += 1
                v = _add(v, self.term(), 1 if op == "+" else -1)
            else:
                return v

    # term := power (('*'|'/'|':'| implicit) power)*
    def term(self) -> Value:
        v = self.power()
        while True:
            k, op = self.peek()
            if k == "op" and op in ("*", "/", ":"):
                self.i += 1
                r = self.power()
                v = _mul(v, r) if op == "*" else _div(v, r)
            elif k in ("num", "sqrt", "var", "pi") or (k == "op" and op == "("):
                # implicit multiplication: 2(3+4), 3x, 2sqrt(2)
                r = self.power()
                v = _mul(v, r)
            else:
                return v

    def power(self) -> Value:
        base = self.unary()
        k, op = self.peek()
        if k == "op" and op == "^":
            self.i += 1
            neg = False
            if self.peek() == ("op", "("):
                self.i += 1
                if self.peek() == ("op", "-"):
                    self.i += 1
                    neg = True
                _, n = self.eat("num")
                self.eat("op", ")")
            else:
                if self.peek() == ("op", "-"):
                    self.i += 1
                    neg = True
                _, n = self.eat("num")
            if "." in n:
                raise Unsupported("fractional exponent")
            e = int(n)
            return _pow(base, -e if neg else e)
        return base

    def unary(self) -> Value:
        k, op = self.peek()
        if k == "op" and op == "-":
            self.i += 1
            return _neg(self.unary())
        if k == "op" and op == "+":
            self.i += 1
            return self.unary()
        return self.atom()

    def atom(self) -> Value:
        k, v = self.peek()
        if k == "num":
            self.i += 1
            val = Poly.const(Fraction(v))
            if self.peek() == ("op", "%"):
                self.i += 1
                return Poly.const(Fraction(v) / 100)
            return val
        if k == "pi":
            self.i += 1
            return Approx(math.pi)
        if k == "var":
            if not self.allow_var:
                raise Unsupported("unknown variable")
            self.i += 1
            return Poly.x(v)
        if k == "sqrt":
            self.i += 1
            if self.peek() == ("op", "("):
                self.i += 1
                inner = self.expr()
                self.eat("op", ")")
            else:
                inner = self.atom()
            return _sqrt(inner)
        if k == "op" and v == "(":
            self.i += 1
            inner = self.expr()
            self.eat("op", ")")
            return inner
        raise Unsupported("syntax")


def _as_poly(v: Value) -> Poly:
    if isinstance(v, Poly):
        return v
    raise Unsupported("not a polynomial")


def _neg(v: Value) -> Value:
    if isinstance(v, Poly):
        return -v
    if isinstance(v, Rad):
        return Rad(-v.coef, v.n)
    return Approx(-float(v))


def _scalar(v: Value) -> Optional[Scalar]:
    if isinstance(v, Poly) and v.is_const():
        return v.const_value()
    if isinstance(v, (Rad, Approx)):
        return v
    return None


def _rad_norm(coef: Fraction, n: int) -> Union[Fraction, Rad]:
    k, m = _squarefree(n)
    coef = coef * k
    if m == 1:
        return coef
    return Rad(coef, m)


def _wrap(s: Union[Fraction, Rad]) -> Value:
    return Poly.const(s) if isinstance(s, Fraction) else s


def _add(a: Value, b: Value, sign: int = 1) -> Value:
    if sign == -1:
        b = _neg(b)
    if isinstance(a, Poly) and isinstance(b, Poly):
        return a + b
    sa, sb = _scalar(a), _scalar(b)
    if sa is None or sb is None:
        raise Unsupported("mixed unknown/irrational")
    if isinstance(sa, Rad) and isinstance(sb, Rad) and sa.n == sb.n:
        c = sa.coef + sb.coef
        return Poly.const(0) if c == 0 else Rad(c, sa.n)
    return Approx(float(sa) + float(sb))


def _mul(a: Value, b: Value) -> Value:
    if isinstance(a, Poly) and isinstance(b, Poly):
        return a * b
    sa, sb = _scalar(a), _scalar(b)
    if sa is None or sb is None:
        raise Unsupported("mixed unknown/irrational")
    if isinstance(sa, Fraction) and isinstance(sb, Rad):
        return Rad(sa * sb.coef, sb.n) if sa != 0 else Poly.const(0)
    if isinstance(sb, Fraction) and isinstance(sa, Rad):
        return Rad(sb * sa.coef, sa.n) if sb != 0 else Poly.const(0)
    if isinstance(sa, Rad) and isinstance(sb, Rad):
        return _wrap(_rad_norm(sa.coef * sb.coef, sa.n * sb.n))
    return Approx(float(sa) * float(sb))


def _div(a: Value, b: Value) -> Value:
    sb = _scalar(b)
    if sb is None:
        raise Unsupported("division by an unknown")
    if isinstance(sb, Fraction):
        if sb == 0:
            raise Unsupported("division by zero")
        if isinstance(a, Poly):
            return a.div_const(sb)
        if isinstance(a, Rad):
            return Rad(a.coef / sb, a.n)
        return Approx(float(a) / float(sb))
    sa = _scalar(a)
    if sa is None:
        raise Unsupported("mixed unknown/irrational")
    if isinstance(sa, (Fraction, Rad)) and isinstance(sb, Rad):
        # a / (c sqrt n) = a sqrt n / (c n)
        num = sa if isinstance(sa, Rad) else Rad(sa, 1)
        if isinstance(sa, Fraction):
            return _wrap(_rad_norm(sa / (sb.coef * sb.n), sb.n))
        if sa.n == sb.n:
            return Poly.const(sa.coef / sb.coef)
        return _wrap(_rad_norm(sa.coef / (sb.coef * sb.n), sa.n * sb.n))
    return Approx(float(sa) / float(sb))


def _pow(a: Value, n: int) -> Value:
    if isinstance(a, Poly):
        if n >= 0:
            return a ** n
        if a.is_const() and a.const_value() != 0:
            return Poly.const(Fraction(1) / (a.const_value() ** -n))
        raise Unsupported("negative power of an unknown")
    s = _scalar(a)
    if isinstance(s, Rad):
        if n >= 0:
            r: Value = Poly.const(1)
            for _ in range(n):
                r = _mul(r, s)
            return r
        inv = _div(Poly.const(1), s)
        return _pow(inv, -n)
    return Approx(float(a) ** n)


def _sqrt(v: Value) -> Value:
    s = _scalar(v)
    if s is None:
        raise Unsupported("sqrt of an unknown")
    if isinstance(s, Fraction):
        return _wrap(sqrt_exact(s))
    if isinstance(s, Rad):
        return Approx(math.sqrt(float(s)))
    return Approx(math.sqrt(float(s)))


def evaluate(text: str, allow_var: bool = False) -> Value:
    """Evaluate a maths expression. Raises ``Unsupported`` if out of scope."""
    s = normalize_math(text)
    if not s.strip():
        raise Unsupported("empty")
    toks = _lex(s)
    p = _Parser(toks, allow_var)
    v = p.expr()
    if p.i != len(toks):
        raise Unsupported("trailing tokens")
    return v


def evaluate_scalar(text: str) -> Scalar:
    """Evaluate a constant expression to Fraction | Rad | Approx."""
    v = evaluate(text)
    s = _scalar(v)
    if s is None:
        raise Unsupported("not a constant")
    return s


# ---------------------------------------------------------------------------
# relations: equations / inequalities in one unknown
# ---------------------------------------------------------------------------

_REL_SPLIT = re.compile(r"<=|>=|!=|=|<|>")


def solve_relation(text: str):
    """Solve a first-degree relation in one unknown.

    Returns ``(op, bound)`` where ``op`` in {'=', '<', '<=', '>', '>='}
    describes the solution set  x op bound,  ``bound`` a Fraction/Rad.
    Returns ``('identity', None)`` or ``('impossible', None)`` for degenerate
    cases. Raises ``Unsupported`` for degree > 1 or several unknowns.
    """
    s = normalize_math(text)
    parts = _REL_SPLIT.split(s)
    ops = _REL_SPLIT.findall(s)
    if len(parts) != 2 or len(ops) != 1:
        raise Unsupported("need exactly one relation")
    op = ops[0]
    left = _as_poly(evaluate(parts[0], allow_var=True))
    right = _as_poly(evaluate(parts[1], allow_var=True))
    diff = left - right  # a x + b  (op) 0
    if diff.degree > 1:
        raise Unsupported("degree > 1")
    a = diff.terms.get(1, Fraction(0))
    b = diff.terms.get(0, Fraction(0))
    if a == 0:
        holds = {"=": b == 0, "<": b < 0, "<=": b <= 0, ">": b > 0,
                 ">=": b >= 0, "!=": b != 0}[op]
        return ("identity", None) if holds else ("impossible", None)
    bound = -b / a
    if a < 0:
        op = {"<": ">", "<=": ">=", ">": "<", ">=": "<=",
              "=": "=", "!=": "!="}[op]
    return op, bound


# ---------------------------------------------------------------------------
# convenience
# ---------------------------------------------------------------------------

def fmt_fraction(q: Fraction) -> str:
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def terminating_decimals(q: Fraction) -> Optional[int]:
    """Number of decimals if q has a finite decimal expansion, else None."""
    d = q.denominator
    twos = fives = 0
    while d % 2 == 0:
        d //= 2
        twos += 1
    while d % 5 == 0:
        d //= 5
        fives += 1
    return max(twos, fives) if d == 1 else None
