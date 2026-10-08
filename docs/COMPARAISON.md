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

## Code public examiné (08/10/2026, lecture seule)

[V] = vérifié dans le texte du dépôt ; le code n'a **pas** été exécuté. « Non trouvé » = nos requêtes n'ont rien donné, pas qu'il n'existe rien.

| Projet | Code public | Licence | Ce que fait le code | Contrôle de fuite / tests / accessibilité (visibles dans le dépôt) |
|---|---|---|---|---|
| DinoBot (Édu-Up 2025) | `Ouiactive/dinobot` : un README d'une ligne, dernier push 2023 [V] | aucune | rien d'exploitable ; lien avec le produit financé non démontré | non trouvé |
| MathPower, Édumalin, AccessDoc, Logbook, Mathia, Adaptiv'Math | non trouvé | n/a | n/a | n/a |
| Vittascience | organisation `vittascience`, 26 dépôts [V] | AGPL-3.0 (plateforme) | plateforme éducative ; module tuteur non localisé | non évalué |
| Sésamath / Coopmaths (MathALÉA, Sésaparcours) | forge.apps.education.fr [V] | AGPL-3.0 | générateurs et moteurs d'exercices, pas des tuteurs LLM | tests sur leur code ; pas de contrôle de fuite LLM |
| PRISME Bot (forge, `applis_maths_sciences`) | oui [V], dernier commit 09/2026 | aucune | tuteur maths/physique-chimie appelant une API LLM hébergée | garde-fous écrits **dans le prompt** (« jamais le résultat final »), détection d'insistance par regex, interface avec ARIA, audit RGPD des CDN ; ni tests ni corpus |
| petits tuteurs d'élèves ou individuels (`tuteur-maths-ia-socratique`, `zimdinos/tuteur-maths`…) | oui [V] | aucune | revendiquent le « socratique » | aucun mécanisme vérifiable, aucun test |

Ce que cela dit, honnêtement : **« ne pas donner la réponse » et l'accessibilité ne suffisent pas, seuls, à nous distinguer** — plusieurs projets les revendiquent. Ce que nous n'avons pas trouvé ailleurs : des contrôles de sortie déterministes dans le code, un corpus exécutable avec ses échecs publiés, des licences permettant la réutilisation. Nous ne pouvons pas parler des produits fermés.
Note : le code Sésamath/Coopmaths est en AGPL-3.0 ; tout couplage doit respecter cette licence.
