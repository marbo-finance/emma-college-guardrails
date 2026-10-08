"""Programme officiel de mathématiques, cycle 4 (4e/3e) — référence déterministe.

Source : programme du cycle 4 (BOEN n°31 du 30-7-2020, en vigueur à la
rentrée 2026 pour la 4e ; transition annoncée : nouvelle 4e en 2027-28,
nouvelle 3e en 2028-29 — voir docs/COMPARISON.md).

    classify("Dans un triangle rectangle...")  -> themes, level, out_of_scope
    prompt_addendum("fr")                      -> text for the system prompt

Keyword-based and conservative: it tags what it recognises and says nothing
otherwise. It never blocks; the harness only *reports* curriculum info.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

__all__ = ["THEMES", "OUT_OF_SCOPE", "classify", "prompt_addendum", "CurriculumInfo"]


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").lower()
    return "".join(c for c in s if not unicodedata.combining(c))


@dataclass
class Theme:
    code: str
    fr: str
    en: str
    level: str          # "4e", "3e" or "cycle4" (both years)
    words: tuple        # folded keywords/regex fragments


THEMES: tuple = (
    Theme("frac", "Fractions, quotients", "Fractions, quotients", "cycle4",
          ("fraction", "quotient", "denominateur", "numerateur", "irreductible")),
    Theme("rel", "Nombres relatifs", "Signed numbers", "cycle4",
          ("relatif", "nombre negatif", "oppose de")),
    Theme("pow", "Puissances", "Powers", "4e",
          ("puissance", "exposant", r"10\^", "notation scientifique")),
    Theme("lit", "Calcul littéral, équations", "Literal calculus, equations", "cycle4",
          ("developpe", "factoris", "equation", "inconnue", "identite remarquable",
           "double distributivite", "reduire l'expression", "inequation")),
    Theme("prop", "Proportionnalité, pourcentages", "Proportionality, percentages", "cycle4",
          ("proportionnel", "pourcentage", "echelle", "vitesse moyenne", "taux")),
    Theme("stat", "Statistiques", "Statistics", "cycle4",
          ("moyenne", "mediane", "etendue", "effectif", "frequence", "diagramme")),
    Theme("prob", "Probabilités", "Probability", "cycle4",
          ("probabilite", "equiprobab", "issue", "evenement", "hasard")),
    Theme("func", "Fonctions (linéaires, affines)", "Functions (linear, affine)", "3e",
          ("fonction", "image de", "antecedent", "lineaire", "affine", "f(x)")),
    Theme("pyth", "Théorème de Pythagore", "Pythagorean theorem", "4e",
          ("pythagore", "hypotenuse", "triangle rectangle")),
    Theme("thal", "Théorème de Thalès", "Intercept (Thales) theorem", "3e",
          ("thales", "triangles semblables", "agrandissement", "reduction")),
    Theme("trig", "Trigonométrie (cos, sin, tan)", "Trigonometry (cos, sin, tan)", "3e",
          ("cosinus", "sinus", "tangente", r"\bcos\b", r"\bsin\b", r"\btan\b")),
    Theme("geo", "Espace et géométrie, transformations", "Space, geometry, transformations", "cycle4",
          ("symetrie", "translation", "rotation", "homothetie", "parallelogramme",
           "mediatrice", "perimetre", "aire ", "volume", "pave droit", "cylindre",
           "cone", "boule", "sphere")),
    Theme("div", "Arithmétique (diviseurs, nombres premiers)", "Arithmetic (divisors, primes)", "3e",
          ("diviseur", "divisible", "nombre premier", "decomposition en facteurs", "pgcd")),
    Theme("algo", "Algorithmique et programmation", "Algorithmics and programming", "cycle4",
          ("scratch", "algorithme", "boucle", "programme qui", "variable informatique")),
)

# Clearly beyond collège (lycée and later): flagged so a tutor reply can be
# brought back to the pupil's level.
OUT_OF_SCOPE: tuple = (
    ("derivee", "dérivée", "derivative"), ("primitive", "primitive", "antiderivative"),
    ("integrale", "intégrale", "integral"), ("logarithme", "logarithme", "logarithm"),
    ("exponentielle", "fonction exponentielle", "exponential function"),
    ("nombre complexe", "nombres complexes", "complex numbers"),
    ("matrice", "matrices", "matrices"), ("limite de", "limites", "limits"),
    ("barycentre", "barycentre", "barycenter"), ("produit scalaire", "produit scalaire", "dot product"),
    ("suite geometrique", "suites", "sequences"), ("suite arithmetique", "suites", "sequences"),
)


@dataclass
class CurriculumInfo:
    themes: list = field(default_factory=list)       # Theme objects
    level: str = ""                                   # "", "4e", "3e", "cycle4"
    out_of_scope: list = field(default_factory=list)  # (fr, en) labels

    def as_dict(self, lang: str = "fr") -> dict:
        fr = lang != "en"
        return {"themes": [(t.fr if fr else t.en) for t in self.themes],
                "level": self.level,
                "out_of_scope": [(a if fr else b) for a, b in self.out_of_scope]}


def classify(text: str) -> CurriculumInfo:
    f = _fold(text)
    info = CurriculumInfo()
    for t in THEMES:
        if any(re.search(w if w.startswith(("\\", "1")) else re.escape(w), f) for w in t.words):
            info.themes.append(t)
    seen = set()
    for key, lab_fr, lab_en in OUT_OF_SCOPE:
        if key in f and lab_fr not in seen:
            seen.add(lab_fr)
            info.out_of_scope.append((lab_fr, lab_en))
    levels = {t.level for t in info.themes}
    if levels == {"cycle4"} or not levels:
        info.level = "cycle4" if levels else ""
    elif "3e" in levels and "4e" in levels:
        info.level = "cycle4"
    else:
        info.level = "3e" if "3e" in levels else "4e"
    return info


def prompt_addendum(lang: str = "fr") -> str:
    fr = lang != "en"
    names = ", ".join((t.fr if fr else t.en) for t in THEMES)
    if fr:
        return ("Cadre du programme (cycle 4, 4e/3e, mathématiques) : " + names + ". "
                "Reste dans ce cadre ; n'utilise jamais d'outils de lycée "
                "(dérivées, logarithmes, limites, nombres complexes…). "
                "Si l'exercice les exige, dis que c'est au-delà du programme de collège.")
    return ("Curriculum frame (French cycle 4, grades 8-9, mathematics): " + names + ". "
            "Stay within it; never use lycée-level tools (derivatives, logarithms, "
            "limits, complex numbers…). If the exercise requires them, say it is "
            "beyond the collège programme.")
