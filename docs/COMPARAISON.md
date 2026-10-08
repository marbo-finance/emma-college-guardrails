# Positionnement d'Emma Collège par rapport à l'existant

*Dernière vérification : 08/10/2026. Les sources sont des pages publiques ; « à vérifier » signifie que nous n'avons pas pu confirmer un point et que nous ne l'affirmons pas. Les corrections sont bienvenues (ouvrir une issue).*

Emma Collège n'est **pas** un produit de tutorat. C'est la **couche de règles**, ouverte et testable, placée entre n'importe quel modèle de langage et un élève de 13 à 15 ans en mathématiques (4e/3e) : ne jamais énoncer la réponse finale, ne jamais féliciter une mauvaise réponse, ne laisser passer aucune donnée personnelle, orienter vers un adulte de confiance en cas de détresse, et adapter la *présentation* aux besoins de l'élève sans jamais enregistrer de diagnostic.

## Ce que nous avons trouvé (et ce que nous n'affirmons pas)

| Projet | Porteur | Code public | Ce que c'est | Rapport avec Emma Collège |
|---|---|---|---|---|
| DinoBot | OuiActive (Édu-Up 01/2025) | aucun vérifié pour le produit | IA socratique en maths, de la 6e au BTS ; « guide sans donner la réponse » | Le plus proche par l'intention. Son mécanisme de garde-fou n'est pas documenté publiquement : **nous n'affirmons pas qu'il n'a pas de détection de fuite**. Notre différence est la *vérifiabilité* : règles et tests publics. |
| MATHIA, Adaptiv'Math, Smart Enseigno | programme P2IA | non ; le ministère a indiqué ne pas publier le code des assistants P2IA (cycle 3) | tuteurs adaptatifs, cycles 2-3 | Complémentaire ; autre niveau (4e/3e), non ouvert. |
| MathPower, Édumalin | lauréats Édu-Up | aucun vérifié | diagnostic / entraînement individualisé | Autre objet (pas de dialogue). |
| AccessDoc | INKLUDO (Édu-Up 04/2024) | aucun vérifié | documents accessibles, maths en LaTeX | Complémentaire (documents, pas tutorat). |
| MathALÉA, Labomep/Sésaparcours, MathGraph32 | Coopmaths, Sésamath | oui, AGPL-3.0 | génération d'exercices, entraînement, géométrie | Sources naturelles d'exercices. Un couplage de code demande de la prudence (AGPL vs Apache-2.0) ; l'échange de *données* est plus simple. |
| OATutor | UC Berkeley CAHLR | oui, MIT | tuteur intelligent ouvert, contenu pré-écrit | Approche différente (contenu rédigé, pas de LLM encadré). Ni francophone ni aligné sur le programme français (à vérifier). |
| MathTutorBench | ETH Zürich | oui, CC BY 4.0 | benchmark de la pédagogie des tuteurs LLM (anglais) | Mesure le *modèle*. Le nôtre mesure une *couche de règles* déterministe, en français, rattachée au programme de 4e/3e. |
| tutor-robustness-eval | EPFL ML4ED | oui (licence non déclarée) | élèves adversariaux qui extraient la réponse, défenses simples | Recherche dont nous nous inspirons ; nous ne revendiquons aucune antériorité. |
| MathCAT, Liblouis | DAISY, liblouis | oui, MIT / LGPL | parole, braille et navigation pour les maths | Nous **déléguons** braille et navigation à ces outils plutôt que de les réinventer. |

## Ce qui nous semble réellement différent (et comment le vérifier)

1. **Un corpus de test public, exécutable, en français, sur le programme de 4e/3e.** `corpus/` contient des centaines de cas rattachés aux objectifs de `catalogs/emma-college-4e-3e.v1.json`, avec réponses qui fuient et réponses légitimes. `python3 -m emma_college bench` reproduit chaque chiffre publié. Nous n'avons trouvé aucun corpus français comparable ; l'absence de preuve n'est pas une preuve d'absence, dites-nous s'il en existe un.
2. **Détection de fuite par équivalence exacte** (fractions, relatifs, équations, radicaux, formes développée/factorisée, arrondis), et pas seulement « le littéral apparaît-il ». Voir la matrice de couverture du README.
3. **Un traitement du handicap conçu comme des préférences, pas des diagnostics** (RGPD art. 9), avec des vérifications de texte déterministes et un rendu oral des mathématiques. Voir `docs/ACCESSIBILITE.md`.
4. **Indépendance vis-à-vis du modèle par construction** : aucun code fournisseur dans le chemin de sécurité.

## Ce que ce n'est pas

Ni une preuve de sécurité, ni un audit RGAA, ni une version validée par des enseignants en exercice (v0.2). Voir *Limites* dans le README.
