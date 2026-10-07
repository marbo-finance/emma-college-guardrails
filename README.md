# Emma Collège — règles de garde-fou et corpus de test

Ce dépôt publie la couche pédagogique de sécurité d'**Emma Collège**, un
prototype de tuteur en mathématiques pour la 4e et la 3e : les règles qui
empêchent le modèle de donner directement la réponse d'un exercice, qui
protègent les données personnelles des enfants, et qui orientent vers un
adulte de confiance en cas de signal de danger — ainsi que le banc de test
qui mesure si ces règles tiennent.

**Ce n'est pas le produit entier.** Le routage multi-modèle, le multi-tenant,
la facturation et le déploiement restent propriétaires — ce qui est publié
ici est la partie que nous pensons devoir être vérifiable par n'importe qui,
pas juste affirmée dans un dossier de subvention.

## Ce que contient ce dépôt

- **`emma_layer.py`** — le contrat pédagogique et les trois couches de
  contrôle :
  - `build_system_prompt` — construit les instructions envoyées au modèle
    (indices, jamais la réponse finale ; pas de fausse louange sur une
    mauvaise réponse ; garde-niveau programme).
  - `firewall_pre` — avant tout appel au modèle : détection d'un signal de
    mise en danger (bascule immédiatement vers un message invitant à parler
    à un adulte de confiance, sans jamais appeler le modèle), rédaction des
    données personnelles (email, téléphone, adresse).
  - `guard_output` / `firewall_post` — après la réponse du modèle : détection
    d'une réponse finale donnée directement (fuite), masquage, et un essai de
    reformulation avant de masquer définitivement.
- **`curriculum.py`** — le format de catalogue d'objectifs pédagogiques
  (niveau, notion, programme), validé strictement à la lecture.
- **`catalogs/emma-fr.v1.json`** — un catalogue d'exemple (CM1/6e aujourd'hui ;
  l'extension 4e/3e, cœur du projet Emma Collège, est en cours).
- **`bench/golden_set.jsonl`** — 51 cas de test annotés : demandes directes de
  réponse, tentatives de contournement ("ignore tes instructions"), données
  personnelles, signaux de mise en danger, tutorat normal, mauvaises réponses
  d'élève.
- **`bench/run_public_bench.py`** — rejoue 42 de ces 51 cas **sans aucun
  modèle** (`guard_output()` est une fonction déterministe, elle évalue une
  paire question/réponse donnée). Les 9 cas restants (historique de
  conversation, injection de rôle) dépendent du serveur multi-tenant privé et
  ne sont pas reproduits ici — indiqué explicitement en `SKIP`, jamais caché.
- **`bench/results-round6.md` / `.json`** — les résultats mesurés en interne
  sur l'ensemble des 51 cas (avec modèle réel) : taux de blocage des fuites
  100 %, taux de faux blocage sur du tutorat normal 0 %, redaction PII 100 %.

## Faire tourner le banc de test

```bash
python3 bench/run_public_bench.py
```

Aucune dépendance externe, aucune clé, aucun modèle requis — stdlib Python
uniquement. Sortie attendue : `42/42 checked cases passed`.

`provider.py` à la racine est un stub documenté : le seul point où
`emma_layer.py` appelle un modèle (une unique tentative de reformulation
après une fuite détectée) passe par `provider.complete()`. Ce fichier montre
l'interface attendue plutôt qu'une intégration réelle — c'est un choix de
conception, pas un oubli : la couche de sécurité ne doit dépendre d'aucun
fournisseur de modèle en particulier.

## Limites, dites à l'avance

- La détection de fuite est heuristique (regex + règles), pas un jugement par
  un second modèle. Elle réduit le risque de fuite, elle ne l'élimine pas.
- Le catalogue actuel couvre CM1/6e ; l'extension 4e/3e est le travail en
  cours pour le projet Emma Collège.
- Les cas d'historique de conversation (injection via un tour précédent,
  usurpation du rôle assistant) sont gérés côté serveur, hors de ce dépôt.

## Licence

- Code (`emma_layer.py`, `curriculum.py`, `provider.py`,
  `bench/run_public_bench.py`) : **Apache License 2.0** — voir `LICENSE`.
- Données (`bench/golden_set.jsonl`, `bench/results-round6.*`,
  `catalogs/*.json`) : **Creative Commons CC BY 4.0**.

Usage commercial autorisé pour l'un comme pour l'autre, sans redevance —
la valeur que nous protégeons (routage multi-modèle, multi-tenant,
déploiement) n'est pas publiée ici.

## Contexte

Publié par **MARBO FINANCE** (Massy) dans le cadre du dossier Édu-Up
« Emma Collège » déposé auprès de la Direction du numérique pour l'éducation
(DNE, ministère de l'Éducation nationale).
