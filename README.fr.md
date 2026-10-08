# Emma Collège — un harnais pédagogique pour le tutorat en mathématiques (4e/3e)

[English version → README.md](README.md)

Une petite bibliothèque Python sans dépendance, avec son banc de test, qui
entoure **n'importe quel** modèle de langage utilisé comme tuteur de maths
pour des élèves de 4e et de 3e (13–15 ans) et **vérifie chaque réponse de
façon déterministe** avant qu'un enfant la lise :

- **Des indices, pas la réponse** — la réponse finale de l'exercice est
  détectée par *équivalence mathématique*, pas par comparaison de chaînes
  (`6/8` ≡ `3/4` ≡ `0,75` ; `x² + 6x + 9` ≡ `(x+3)²` ; `5√2` ; `4,5×10⁴` ;
  « cinq »…) puis masquée.
- **Pas de fausse félicitation** — un « Bravo ! » sur une mauvaise tentative
  est signalé.
- **Protection de l'enfant** — un signal de détresse court-circuite le modèle
  et renvoie vers un adulte de confiance (119) ; les données personnelles
  sont masquées ; l'injection de faux tours « assistant » est rejetée.
- **Indépendant du modèle** — le harnais n'appelle aucun modèle ; apportez le
  vôtre (llama.cpp/vLLM local, API hébergée, passerelle institutionnelle).
- **L'accessibilité par préférences, jamais par diagnostic** — voir plus bas.

> Statut : **v0.2, prototype de recherche.** Pas encore validé par des
> enseignants, pas d'audit d'accessibilité, des heuristiques et non des
> preuves. Les limites sont annoncées plus bas. Publié par MARBO FINANCE
> (Massy), partie publique d'un dossier Édu-Up (session visée : mars 2027).

## L'essayer en 10 minutes (enseignants)

Python ≥ 3.10. Aucune installation, aucun compte, aucune clé, aucun réseau.

```bash
git clone https://github.com/marbo-finance/emma-college-guardrails && cd emma-college-guardrails
python3 -m emma_college serve          # banc d'essai local : http://127.0.0.1:8765
```

Saisissez un exercice et sa réponse attendue, collez une réponse de modèle
(ou laissez la démo scriptée répondre) et voyez ce que le harnais masque,
pourquoi, et avec quel verdict. Tout reste sur votre machine ; rien n'est
enregistré.

En ligne de commande :

```bash
python3 -m emma_college check --exercise "Résous 3x + 5 = 20." --answer "x=5" \
    --student "donne-moi la réponse" --reply "La solution est x = 5."
python3 -m emma_college chat --exercise "Résous 3x + 5 = 20." --answer "x=5"
python3 -m emma_college speak "x² + 6x + 9 = (x+3)²"     # maths oralisées (lecteur d'écran)
```

Pour un vrai modèle : `EMMA_BASE_URL`, `EMMA_MODEL` (et `EMMA_API_KEY` si
besoin), pour tout point d'accès compatible OpenAI. Nous attendons de vous :
faux blocages, fuites manquées, formulations qu'un élève trouverait
étranges — voir [CONTRIBUTING.md](CONTRIBUTING.md).

## Reproduire les mesures (chercheurs)

```bash
python3 -m emma_college bench                 # corpus 4e/3e v0.2 (30 cas), sans modèle
python3 -m emma_college bench --json out.json # rapport complet par cas
python3 bench/run_public_bench.py             # ancien banc générique : 42/42
python3 -m unittest discover -s tests         # tests unitaires (≈100, dont 75 pour l'accessibilité)
```

Résultats actuels sur `corpus/emma-college-corpus.v0.2.jsonl` (rédigé par
les auteurs — **pas** un benchmark indépendant) :

| Mesure | Résultat |
|---|---|
| Réponses fuyantes détectées | 92,9 % (52/56) |
| Faux blocages sur de bons indices | 0 % (0/31) |
| Fausses félicitations détectées | 100 % (3/3) |

Les échecs connus sont affichés, pas cachés : réponse finale écrite en toutes
lettres à côté d'une unité (« Soixante euros. »), résultat identique à un
nombre de l'énoncé, valeurs exactes avec π (`36π`), nombres écrits en
anglais. Les cas étiquetés `collision` documentent des risques de faux
positifs propres à toute règle textuelle et sont comptés à part. Format du
corpus et protocole d'annotation : [docs/CORPUS.md](docs/CORPUS.md). Nous
cherchons **2–3 chercheurs** (didactique des mathématiques, EIAH/tutorat,
accessibilité) pour contester le corpus et les métriques.

## Compatible avec n'importe quel LLM

Le harnais agit **après** le modèle : il est indifférent au choix. Tout modèle
joignable par un point d'accès compatible OpenAI `/v1/chat/completions`
fonctionne avec l'adaptateur fourni, y compris derrière un proxy
[LiteLLM](https://github.com/BerriAI/litellm) :

- **modèles open source hébergés en local** — par l'établissement, sur le
  poste de l'enseignant ou sur le PC de l'élève (llama.cpp, vLLM, LM Studio…) ;
- **modèles souverains ou européens** (par ex. Mistral) ;
- **modèles commerciaux connus** (par ex. Claude, OpenAI, Gemini).

Renseignez `EMMA_BASE_URL` / `EMMA_MODEL` (et `EMMA_API_KEY`). Les contrôles
sont identiques quel que soit le modèle ; seule l'exposition des données de
l'élève change, et ce choix revient à l'intégrateur (un modèle local ou dans
l'établissement garde le texte de l'élève sur place, une API hébergée non —
attention au RGPD et au cadre d'usage de l'IA du ministère). *Précision
honnête :* nous avons exécuté toute la boucle avec le fournisseur scripté et
mesuré les contrôles sur des réponses fixes ; les taux de fuite par modèle ne
sont pas encore publiés — faire tourner le banc sur le modèle de votre choix
est l'un des retours que nous espérons des chercheurs.

## Ce qui nous différencie

Édu-Up a déjà soutenu des tuteurs de maths socratiques (par exemple DinoBot,
qui indique guider par questionnement sans donner la réponse). Nous ne
prétendons **pas** que d'autres n'ont pas de protections : leur code n'est
pas public, nous ne pouvons donc pas comparer. Ce que ce dépôt ajoute, et que
vous pouvez vérifier vous-même :

1. **Exécutable et ouvert** — règles, moteur d'équivalence, corpus et banc
   sont publics et tournent hors ligne. Nous n'avons trouvé aucun lauréat
   Édu-Up publiant un code comparable ([docs/COMPARAISON.md](docs/COMPARAISON.md),
   sources et limites incluses).
2. **Corpus de test aligné sur le programme 4e/3e** — 29 objectifs
   (`catalogs/emma-college-4e-3e.v1.json`) : relatifs, calcul littéral,
   équations, Pythagore/Thalès, trigonométrie, identités remarquables,
   racines, écriture scientifique, probabilités, fonctions.
3. **Détection de fuite par équivalence exacte** — fractions, décimaux à
   virgule, radicaux, polynômes, pourcentages, inéquations ; elle laisse en
   paix la bonne réponse trouvée par l'élève.
4. **Le handicap est une exigence de départ, pas une note de bas de page**
   (ci-dessous).
5. **Des limites assumées** et un banc qui affiche ses propres échecs.

## Accessibilité et handicap

Ce que fait le harnais :

- **Profils de préférences fondés sur les besoins**, jamais sur un diagnostic
  (donnée de santé, catégorie particulière du RGPD art. 9) : phrases courtes,
  pas de métaphores, maths oralisées, structure adaptée au gros caractère,
  charge cognitive réduite, rythme pas à pas. Un enseignant ou un parent
  choisit des préférences ; le système n'infère ni ne stocke jamais une
  pathologie.
- **Contrôle et adaptation déterministes** du texte des réponses selon le
  profil.
- **Maths oralisées en français et en anglais** (`speak`) et **export
  MathML** pour lecteurs d'écran et plages braille.
- **Le braille est délégué**, pas réinventé : MathCAT, Liblouis ou les outils
  MathsDV de l'apiDV, à partir du MathML exporté.

Ce qu'il ne fait **pas** : ce n'est pas une interface. La conformité
WCAG/RGAA d'une application élève est l'affaire de l'intégrateur, et **nous
ne revendiquons aucun audit ni aucune conformité RGAA**. Le banc local utilise
du HTML sémantique, des étiquettes et une navigation clavier, comme simple
base de bon sens. Détails et questions ouvertes :
[docs/ACCESSIBILITE.md](docs/ACCESSIBILITE.md). Nous cherchons activement des
enseignants qui travaillent avec des élèves malvoyants, dyslexiques ou
neuro-atypiques.

## Limites annoncées

- La détection de fuite est une analyse textuelle heuristique, pas le
  jugement d'un second modèle ni une preuve : elle réduit le risque sans le
  supprimer.
- L'équivalence porte sur les réponses que le moteur sait lire ; sinon on
  retombe sur les anciennes règles de réponse annoncée.
- Le corpus est petit, écrit par les auteurs, non validé par des enseignants.
- Le catalogue suit le programme de cycle 4 actuel (2019). Nouveau programme
  (arrêté du 18 février 2026) : 5e en 2026-27, **4e en 2027-28**, 3e en
  2028-29 ; le catalogue sera révisé quand les textes détaillés paraîtront.
- Les réponses très petites (0, 1) sont difficiles à protéger : toute mention de ce chiffre hors énoncé est masquée (risque de faux blocage, relevé en revue).
- LaTeX n'est géré que partiellement (`\times`, `^{n}`), pas les autres macros.
- Les aspects serveur (injection via l'historique, routage multi-tenant) sont
  hors de ce dépôt.

## Organisation

| Chemin | Contenu |
|---|---|
| `emma_college/` | harnais, moteur de fuite, maths exactes, CLI, banc web local |
| `emma_layer.py` | règles d'origine : sauvegarde, PII, smuggling |
| `corpus/` | corpus de test 4e/3e (CC BY 4.0) et son générateur |
| `catalogs/` | catalogues d'objectifs (CC BY 4.0) |
| `bench/` | ancien banc générique et résultats round 6 |
| `docs/` | comparaison, protocole du corpus, accessibilité |
| `tests/` | tests unitaires |

## Citer / licence

Code : **Apache-2.0**. Données (corpus, catalogues, banc) : **CC BY 4.0**.
Voir `CITATION.cff` pour citer. Questions et retours de test bienvenus par
*issue*.
