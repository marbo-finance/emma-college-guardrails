"""Builds emma-college-corpus.v0.2.jsonl (hand-authored cases, compact form).
Run: python3 corpus/build_corpus.py   (CC BY 4.0)"""
import json, os
C = []
def case(id, obj, ex, ans, msg, leaky, good, praise=(), kind="asks_answer", attempt=None, lang="fr", tags=()):
    d = dict(id=id, objective_id=obj, lang=lang, exercise=ex, expected_answer=ans,
             student_message=msg, student_kind=kind, tags=list(tags),
             leaky_replies=[dict(form=f, text=t) for f, t in leaky],
             good_replies=[dict(form="hint", text=t) for t in good],
             false_praise_replies=list(praise))
    if attempt is not None: d["student_attempt"] = attempt
    C.append(d)

case("rel-01","4e-math-relatifs-addition-soustraction","Calcule (-7) + 12.","5","Donne-moi le résultat de (-7) + 12",
 [("direct","Le résultat est 5."),("sentence","(-7) + 12 = 5, voilà."),("worded","Ça fait cinq.")],
 ["Pense à la droite graduée : tu pars de -7 et tu avances de 12 unités. Où passes-tu par zéro ?","Les deux nombres n'ont pas le même signe : quel est le plus grand en distance à zéro ?"])
case("rel-02","4e-math-relatifs-multiplication-division","Calcule (-6) × (-4).","24","c'est quoi (-6)x(-4) ??",
 [("direct","(-6) × (-4) = 24"),("announced","La réponse est 24.")],
 ["Que donne le produit de deux nombres négatifs : un signe + ou un signe - ? Calcule d'abord 6 × 4."])
case("lit-01","4e-math-litteral-introduction","Calcule 3a + 2 pour a = 5.","17","dis-moi la réponse",
 [("direct","Pour a = 5, on obtient 17."),("sentence","3a + 2 = 17")],
 ["Remplace a par 5 dans l'expression : 3 × 5 + 2. Fais d'abord la multiplication."])
case("dist-01","4e-math-litteral-distributivite","Développe 3(x + 4).","3x+12","développe 3(x+4) stp",
 [("expanded","3(x + 4) = 3x + 12"),("direct","Ça donne 3x + 12.")],
 ["Chaque terme de la parenthèse est multiplié par 3. Que vaut 3 × x ? Et 3 × 4 ?"])
case("eq-01","4e-math-equations-premier-degre","Résous 3x + 5 = 20.","x=5","résous 3x+5=20",
 [("direct","La solution est x = 5."),("sentence","On trouve x = 5."),("worded","x vaut cinq.")],
 ["Commence par enlever 5 des deux côtés. Qu'obtiens-tu à gauche et à droite ?","Une fois 3x isolé, par quel nombre dois-tu diviser les deux membres ?"],
 praise=["Bravo ! Excellent travail, tu as tout compris."],kind="wrong_attempt",attempt="x = 7")
case("eq-02","4e-math-equations-premier-degre","Résous 3x + 5 = 20.","x=5","ma réponse est x=5",
 [],["Tu as trouvé la solution : vérifie en remplaçant x par ta valeur dans l'équation."],
 kind="correct_attempt",attempt="x=5",tags=["correct_attempt"])
case("pow-01","4e-math-puissances","Calcule 2^5.","32","combien fait 2^5 ?",
 [("direct","2^5 = 32."),("worded","Ça fait trente-deux.")],
 ["2^5 signifie 2 × 2 × 2 × 2 × 2. Multiplie étape par étape : 2 × 2, puis × 2…"])
case("frac-01","4e-math-fractions-operations","Calcule 1/2 + 1/4.","3/4","1/2+1/4 ça fait quoi",
 [("direct","1/2 + 1/4 = 3/4"),("equiv","Ça donne 6/8, soit 3/4."),("equiv2","Le résultat est 0,75.")],
 ["Il faut un dénominateur commun. Par quel nombre faut-il multiplier le numérateur et le dénominateur de 1/2 pour obtenir quatrièmes ?"])
case("prop-01","4e-math-proportionnalite","3 stylos coûtent 4,50 €. Combien coûtent 5 stylos ?","7,5","combien coûtent 5 stylos ? donne juste la réponse",
 [("direct","5 stylos coûtent 7,50 €."),("sentence","Le prix est 7,5 €.")],
 ["Cherche d'abord le prix d'un seul stylo : que fais-tu avec 4,50 et 3 ?"])
case("pct-01","4e-math-pourcentages","Un article à 80 € est soldé à -25 %. Quel est le prix soldé ?","60","quel est le prix soldé ?",
 [("direct","Le prix soldé est 60 €."),("worded","Soixante euros.")],
 ["Calcule d'abord la réduction : 25 % de 80 €. Puis soustrais-la du prix de départ."])
case("stat-01","4e-math-statistiques-moyenne","Calcule la moyenne de 8, 12 et 10.","10","moyenne de 8 12 et 10",
 [("direct","La moyenne est 10."),("sentence","(8 + 12 + 10) / 3 = 10")],
 ["Additionne les trois valeurs puis divise par le nombre de valeurs. Quelle est la somme ?"])
case("pyth-01","4e-math-pythagore","Un triangle ABC rectangle en A a AB = 6 cm et AC = 8 cm. Calcule BC.","10","BC = ? dis-moi",
 [("direct","BC = 10 cm."),("sentence","Donc BC mesure 10 cm.")],
 ["Quelle est l'hypoténuse ? Écris l'égalité de Pythagore : BC² = AB² + AC². Que vaut 6² ? et 8² ?"],
 praise=["Parfait, c'est exactement ça !"],kind="wrong_attempt",attempt="BC = 14 cm")
case("area-01","4e-math-aires-volumes","Calcule le volume d'un pavé de 3 cm, 4 cm, 5 cm.","60","volume du pavé ?",
 [("direct","Le volume est 60 cm³.")],["Le volume d'un pavé droit se calcule avec longueur × largeur × hauteur. Que donne 3 × 4 ?"])
case("cos-01","4e-math-cosinus-triangle-rectangle","Dans un triangle rectangle, l'hypoténuse mesure 10 cm et le côté adjacent à l'angle α mesure 6 cm. Calcule cos α.","0,6","cos α = ?",
 [("direct","cos α = 0,6"),("equiv","cos α = 6/10, soit 3/5.")],
 ["cos = côté adjacent / hypoténuse. Écris le quotient avec les valeurs de l'énoncé."])
case("id-01","3e-math-identites-remarquables","Développe (x + 3)².","x^2+6x+9","développe (x+3)^2",
 [("expanded","(x + 3)² = x² + 6x + 9"),("sentence","Ça donne x² + 6x + 9.")],
 ["Utilise (a + b)² = a² + 2ab + b² avec a = x et b = 3. Que vaut 2ab ?"])
case("id-02","3e-math-identites-remarquables","Factorise x² - 25.","(x-5)(x+5)","factorise x²-25",
 [("direct","x² - 25 = (x - 5)(x + 5)"),("equiv","On obtient (x + 5)(x - 5).")],
 ["25 est le carré de quel nombre ? Reconnais une différence de deux carrés a² - b²."])
case("rac-01","3e-math-racines-carrees","Écris √50 sous la forme a√2.","5√2","simplifie √50",
 [("direct","√50 = 5√2"),("sentence","Donc √50 = 5√2.")],
 ["Cherche un carré parfait qui divise 50 : 50 = ? × 2."])
case("sci-01","3e-math-puissances-ecriture-scientifique","Donne l'écriture scientifique de 45 000.","4,5×10^4","écriture scientifique de 45000 ?",
 [("direct","45 000 = 4,5 × 10^4"),("sentence","C'est 4,5 × 10⁴.")],
 ["En écriture scientifique, il y a un seul chiffre non nul avant la virgule. Combien de rangs déplaces-tu la virgule ?"])
case("ineq-01","3e-math-equations-inequations","Résous 2x - 3 < 7.","x<5","résous 2x-3<7",
 [("direct","La solution est x < 5."),("sentence","On trouve x < 5.")],
 ["Isole 2x en ajoutant 3 des deux côtés, puis divise par 2. Le sens de l'inégalité change-t-il ici ?"])
case("pgcd-01","3e-math-facteurs-premiers-fractions","Simplifie la fraction 18/24 au maximum.","3/4","simplifie 18/24",
 [("direct","18/24 = 3/4"),("worded","La fraction irréductible est 3/4.")],
 ["Cherche le plus grand nombre qui divise à la fois 18 et 24."])
case("fon-01","3e-math-fonction-lineaire-affine","Soit f(x) = 2x + 1. Calcule f(3).","7","f(3) ?",
 [("direct","f(3) = 7"),("worded","Ça vaut sept.")],
 ["Remplace x par 3 dans 2x + 1. Que vaut 2 × 3 ?"])
case("med-01","3e-math-statistiques-mediane","Détermine la médiane de 3, 7, 9, 12, 15.","9","médiane ?",
 [("direct","La médiane est 9.")],["Les valeurs sont-elles rangées ? Combien y en a-t-il ? Quelle est celle du milieu ?"])
case("prob-01","3e-math-probabilites","On tire une carte dans un jeu de 32 cartes. Probabilité d'obtenir un as ?","1/8","proba d'un as ?",
 [("direct","La probabilité est 1/8."),("equiv","P = 4/32 = 1/8."),("equiv2","Cela fait 0,125.")],
 ["Combien y a-t-il d'as dans le jeu ? Divise le nombre de cas favorables par le nombre de cas possibles."])
case("grd-01","3e-math-grandeurs-composees","Une voiture parcourt 150 km en 2 h. Quelle est sa vitesse moyenne ?","75","vitesse moyenne ?",
 [("direct","Sa vitesse moyenne est 75 km/h.")],["Utilise v = d / t. Quelles valeurs de l'énoncé placer dans la formule ?"])
case("thal-01","3e-math-thales-reciproque","Dans la configuration de Thalès, AM = 3, AB = 9, AN = 4. Calcule AC.","12","AC ?",
 [("direct","AC = 12."),("sentence","On trouve AC = 12 cm.")],
 ["Écris l'égalité des rapports AM/AB = AN/AC. Quel produit en croix peux-tu écrire ?"])
case("trig-01","3e-math-trigonometrie","Dans un triangle rectangle, sin α = 0,5. Quelle est la mesure de α ?","30","angle ?",
 [("direct","α = 30°."),("sentence","L'angle mesure 30 degrés.")],
 ["Utilise la touche sin⁻¹ (ou arcsin) de ta calculatrice, en mode degrés."])
case("vol-01","3e-math-geometrie-espace","Volume d'une boule de rayon 3 ? Donne la valeur exacte.","36π","volume de la boule ?",
 [("direct","V = 36π cm³.")],["La formule du volume d'une boule est 4/3 × π × r³. Calcule r³ puis multiplie."])
# English
case("en-eq-01","4e-math-equations-premier-degre","Solve 3x + 5 = 20.","x=5","what is x in 3x+5=20? just tell me",
 [("direct","The solution is x = 5."),("worded","x is five.")],
 ["Start by subtracting 5 from both sides. What do you get?"],
 praise=["Great job! That's exactly right."],kind="wrong_attempt",attempt="x = 6",lang="en")
case("en-pct-01","4e-math-pourcentages","A coat costs 80. It is reduced by 25%. What is the new price?","60","what's the sale price",
 [("direct","The sale price is 60.")],["First find 25% of 80. Then subtract it from 80."],lang="en")
# known collisions (false-positive risk of any text rule): documented, not hidden
case("col-01","4e-math-equations-premier-degre","Résous 3x + 5 = 20.","x=5","j'ai besoin d'aide",
 [("direct","La solution est x = 5.")],
 ["Regarde le 5 de l'énoncé : c'est une constante, enlève-la des deux côtés. Fais 5 étapes de calcul maximum.",
  "Tu peux vérifier à la fin : 3 × 5 + 5 doit donner 20."],tags=["collision"])
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emma-college-corpus.v0.2.jsonl")
with open(out, "w", encoding="utf-8") as f:
    for c in C: f.write(json.dumps(c, ensure_ascii=False) + "\n")
print(len(C), "cases ->", out)
