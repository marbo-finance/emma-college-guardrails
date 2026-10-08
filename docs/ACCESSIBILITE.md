# Couche d'accessibilité (`emma_college.access`)

Emma Collège est une couche de garde-fous pédagogiques pour un tuteur de maths à base d'IA (collège, 4e/3e, 13-15 ans). Ce module rend le *texte* du tuteur plus facile à utiliser pour des élèves aux besoins d'accès différents, sans affaiblir le contrat pédagogique. Il est déterministe, n'utilise que la bibliothèque standard et est publié sous licence Apache 2.0.

> **Statut : travail en cours, pas une certification d'accessibilité.** Rien ici n'affirme la conformité au RGAA, aux WCAG ou à la norme EN 301 549. Le module vérifie et transforme du texte ; la conformité ne peut s'établir que par l'audit de l'interface entière (sections 5 et 6).

English version: [ACCESSIBILITY.md](ACCESSIBILITY.md).

## 1. Notre position (les principes de conception)

1. **Des profils de préférences fondés sur les besoins, pas sur des diagnostics.** Les données de santé et de handicap sont une catégorie particulière au sens de l'article 9 du RGPD. Le système ne demande jamais de diagnostic, n'en stocke aucun et n'en déduit aucun de ce que l'élève écrit : pas de profilage de l'enfant. Un *profil* est un ensemble nommé de préférences de présentation (`lecture_vocale`, `texte_aere`, `une_etape_a_la_fois`, `langage_litteral`, `sans_pression_temps`, `contraste_zoom`...) **choisi par l'élève, un parent ou l'enseignant** et **conservé localement (sur l'appareil) par l'intégrateur**. Les noms de profils désignent un *besoin* ou une *préférence*. Un profil ne contient aucun champ de texte libre ni aucune donnée de l'élève. Plusieurs profils se combinent (`combine_profiles`) : la limite la plus stricte l'emporte.
2. **L'accessibilité n'affaiblit jamais le contrat pédagogique.** Des indices, pas des réponses : la règle reste vraie. `profile_prompt_addendum()` le rappelle dans chaque addendum non neutre, et `adapt()` ne change que la forme (espaces, retours à la ligne, limites de phrases, emoji) : jamais le contenu mathématique, jamais un chiffre modifié, jamais une valeur numérique ajoutée (c'est testé). Une réponse adaptée doit toujours passer le contrôle de fuite ; ce contrôle vit dans un autre module (`emma_college/leak.py`), à appliquer en dernier sur `AdaptedReply.text` (et sur `.spoken` si on le lit à voix haute).
3. **La couche déterministe ne traite que le texte.** Elle sait analyser et transformer une réponse. L'ordre de focus, le contraste, l'usage au clavier, ARIA, le zoom et le reflow relèvent de l'interface qui intègre le module et de son audit RGAA 4.1 / WCAG 2.2 AA. La section 5 liste ce que l'interface de démonstration doit faire.
4. **Des limites assumées.** La section 6 liste ce qui n'est pas couvert. En particulier : la sortie braille est déléguée aux lecteurs d'écran et à des outils externes (par exemple le projet « MathsDV » de l'apiDV), il n'y a pas de langue des signes, et pas de saisie manuscrite (dysgraphie).

## 2. Les profils

Un profil est une dataclass figée : `name, label_fr, label_en, needs, max_sentence_words, max_steps_per_reply, forbid_figurative, forbid_time_pressure, spoken_math, limit_symbols, limit_emoji`. `PROFILES` associe un nom à son profil. Les « besoins » sont des besoins de présentation (vocabulaire `NEEDS`), pas des pathologies.

| Profil | Besoin(s) de présentation couvert(s) | Usage typique | Ce que la couche vérifie (`lint`) et adapte (`adapt`) |
|---|---|---|---|
| `default` | aucun | pas d'adaptation | contrôles universels seulement : référence par la couleur seule, MAJUSCULES, paragraphes très longs |
| `lecture_vocale` | `lecture_ecran`, `acces_audio` | élève qui lit avec un lecteur d'écran, une plage braille ou une synthèse vocale (cécité, basse vision) | phrases de 20 mots au plus, 3 étapes au plus, pas d'emoji, pas de flèches, de dessins en caractères ni de tableaux, pas de renvoi purement visuel, LaTeX brut signalé ; `adapt` produit la forme parlée et le MathML |
| `contraste_zoom` | `vision_reduite`, `agrandissement` | élève qui a besoin de fort contraste et de zoom (200 % à 400 %) | phrases de 18 mots au plus, 3 étapes au plus, 1 emoji au plus, pas de symbole inexpliqué, renvois purement visuels signalés (info) |
| `texte_aere` | `lecture_fluente` | élève pour qui un texte dense est fatigant à lire | phrases de 14 mots au plus, 3 étapes au plus, 2 emoji au plus ; `adapt` coupe les phrases longues à une conjonction sûre et met une étape par ligne |
| `nombres_clairs` | `nombres_symboles`, `charge_cognitive` | élève qui a besoin que nombres et symboles soient lus clairement, peu de choses à la fois | phrases de 15 mots au plus, 2 étapes ou questions au plus, 1 emoji au plus, pas de symbole inexpliqué ; forme parlée et MathML |
| `une_etape_a_la_fois` | `attention_soutenue`, `charge_cognitive` | élève qui travaille mieux une chose à la fois | phrases de 12 mots au plus, **une** étape et une question par réponse, aucune pression de temps, 1 emoji au plus |
| `langage_litteral` | `langage_litteral`, `previsibilite` | élève qui a besoin d'un langage littéral et d'une structure prévisible | aucune expression imagée ni idiome, aucune pression de temps, aucun emoji, phrases de 15 mots au plus ; l'addendum demande la même structure à chaque message |
| `sans_pression_temps` | `rythme_personnel`, `previsibilite` | élève qui a besoin d'avancer à son rythme | aucun mot de pression de temps (« vite », « chrono », « en moins de », « hurry »...) |
| `texte_prioritaire` | `texte_prioritaire` | élève pour qui le son n'est pas fiable | aucun indice sonore seul (« écoute », « comme j'ai dit »), information toujours écrite, phrases de 18 mots au plus |
| `reponses_courtes` | `motricite_fine` | élève pour qui la saisie est lente ou fatigante | pas de demande de saisie lourde (« rédige un paragraphe », « recopie »), 2 étapes au plus, réponses sous forme de nombre, de mot ou de choix |

Les profils sont volontairement nommés par besoin et par préférence. Nous ne prétendons pas qu'un besoin corresponde à une pathologie donnée : beaucoup d'élèves ayant la même pathologie ont des besoins différents, et beaucoup d'élèves sans diagnostic partagent les mêmes besoins.

### Codes de `lint`

| Code | Gravité | Signification |
|---|---|---|
| `LONG_SENTENCE` | warn | plus de mots que le profil n'en autorise |
| `TOO_MANY_STEPS`, `TOO_MANY_QUESTIONS` | warn | plus d'étapes numérotées ou de questions que permis dans une réponse |
| `FIGURATIVE` | warn | idiome ou expression imagée (environ 70 expressions françaises et 40 anglaises, variantes comprises, dans `access_data/lexicons.json`) |
| `TIME_PRESSURE` | warn | vocabulaire d'urgence, avec une garde simple contre la négation (« pas besoin d'aller vite » est accepté) |
| `SYMBOL_UNEXPLAINED` | warn | flèches, `≈`, `∴`, formes géométriques, flèches ASCII mal lues par les lecteurs d'écran |
| `ASCII_ART`, `TABLE` | warn | caractères de tracé, lignes de séparation, dessins en caractères, tableaux en texte |
| `EMOJI_EXCESS` | warn | plus d'emoji que le profil n'en autorise |
| `COLOR_ONLY` | warn | référence par la couleur seule (« la case rouge ») ; tous les profils |
| `VISUAL_DEIXIS` | warn / info | « comme tu peux le voir », « ci-dessus », « à gauche » (warn pour les profils lecteur d'écran, info pour la basse vision) |
| `AUDIO_ONLY_CUE` | warn | « écoute bien », « comme j'ai dit » (profil texte d'abord) |
| `CAPS_SHOUTING` | info | mot en MAJUSCULES (hors sigles et noms de points comme `ABCD`) ; tous les profils |
| `LONG_PARAGRAPH` | info | paragraphe très long d'un seul bloc ; tous les profils |
| `RAW_LATEX` | warn | LaTeX non rendu dans un profil vocal |
| `TYPING_HEAVY` | warn | demande de longues réponses saisies (profil motricité) |

Les lexiques sont de simples fichiers JSON, faits pour être enrichis par pull request ; chaque ajout doit s'accompagner d'un cas de corpus.

## 3. API

```python
from emma_college.access import (PROFILES, spoken_math, to_mathml, lint, adapt,
                                 profile_prompt_addendum, explain_profile, combine_profiles)

spoken_math("AB = 5 cm")                 # 'A B égale cinq centimètres'
spoken_math("3/4", "fr", style="natural") # 'trois quarts'
to_mathml("x^2 + 1 = 5")                  # '<math xmlns=... alttext="x au carré plus un égale cinq">...'
lint(reply, "langage_litteral")           # list[Finding(code, severity, message_fr, message_en, span)]
r = adapt(reply, "lecture_vocale")        # AdaptedReply(text, spoken, mathml, findings)
system_prompt += profile_prompt_addendum("une_etape_a_la_fois")
```

* `lint` est déterministe et piloté par le profil ; `lang` choisit le lexique d'idiomes et d'indices.
* `adapt` est prudent : il retire les emoji au-delà de la limite du profil, place chaque étape numérotée sur sa propre ligne, ne coupe une phrase trop longue qu'à une conjonction sûre (`, mais`, `, puis`, `, donc`, `, car`, `;`... jamais dans une parenthèse ni une énumération) et, pour les profils vocaux, produit `spoken` et `mathml`. `findings` contient les constats restants sur le texte adapté, suivis des entrées d'audit `ADAPT_*` (ce qui a été modifié). Il ne **réécrit pas** les idiomes ni la pression de temps : il les signale, pour que l'intégrateur redemande une génération au modèle avec l'addendum.
* `to_mathml` accepte un sous-ensemble sûr (nombres, identifiants, `+ − × ÷ =`, inégalités, `\frac`, `a/b` entre opérandes simples, exposants, indices, `\sqrt`, parenthèses, unités, degrés). Il n'utilise jamais `eval`, échappe tout le texte et lève `ValueError` hors du sous-ensemble. L'attribut `alttext` porte la forme parlée.
* Choix d'intégration : garder les `$...$` dans `AdaptedReply.text` et substituer les éléments de `mathml` dans l'ordre à l'affichage (le MathML n'est pas lu de la même façon par toutes les technologies d'assistance, gardez donc `alttext`), ou lire `spoken` directement.

## 4. Mathématiques parlées

Le style par défaut est explicite et sans ambiguïté (`trois sur quatre`) ; `style="natural"` donne `un demi`, `un tiers`, `deux tiers`, `un quart`, `trois quarts` uniquement pour ces fractions. Les nombres négatifs se disent `moins sept` ; les parenthèses sont annoncées (`parenthèse ouverte ... parenthèse fermée`) ; une fraction complexe est annoncée avec son numérateur et son dénominateur pour que rien ne dépende de l'ordre de lecture. Les nombres français jusqu'à 999 999 999 suivent les règles de 70/80/90 (`soixante et onze`, `quatre-vingts` / `quatre-vingt-un`, `deux cents` / `deux cent un`, `et un`, accord de `cent`) et l'accord des unités (`1,5 kg` reste au singulier, `21 min` se lit `vingt et une minutes`).

| Entrée | Français | Anglais |
|---|---|---|
| `x = 5` | x égale cinq | x equals five |
| `−7` | moins sept | minus seven |
| `x²` | x au carré | x squared |
| `x^4` | x puissance quatre | x to the power of four |
| `√2` | racine carrée de deux | square root of two |
| `$\frac{3}{4}$` | trois sur quatre | three over four |
| `\frac{a+b}{c}` | la fraction de numérateur a plus b et de dénominateur c | the fraction with numerator a plus b and denominator c |
| `2,5` | deux virgule cinq | two point five |
| `1 000` | mille | one thousand |
| `x ≤ 3` | x inférieur ou égal à trois | x less than or equal to three |
| `AB = 5 cm` | A B égale cinq centimètres | A B equals five centimeters |
| `35°` | trente-cinq degrés | thirty-five degrees |
| `(−3)²` | parenthèse ouverte moins trois parenthèse fermée au carré | open parenthesis minus three close parenthesis squared |
| `50 km/h` | cinquante kilomètres par heure | fifty kilometers per hour |
| `20 %` | vingt pour cent | twenty percent |
| `12/05/2026` | douze mai deux mille vingt-six | twelve slash five slash two thousand twenty-six |

Conventions et pièges connus (tous couverts par les tests) : un point ou une virgule entre chiffres est toujours un séparateur décimal (`1,2,3` se lit un décimal puis `3`) ; une unité d'une seule lettre collée au nombre (`3t`, `2m`) est lue comme une variable, donc `m`, `g`, `t`, `s`, `l` exigent une espace après le nombre ; un trait d'union sans espace entre deux chiffres est lu comme un moins (`10-15` donne `dix moins quinze`), il faut donc écrire les intervalles en toutes lettres ; le prompt système demande au modèle d'écrire le signe moins `−` entouré d'espaces. Au-delà de 999 999 999, les nombres sont lus chiffre par chiffre.

## 5. Ce que l'interface qui intègre le module doit fournir

Le module ne peut pas le fournir. C'est la liste de contrôle de l'interface de démonstration et de tout intégrateur, alignée sur le RGAA 4.1 (fondé sur les WCAG 2.1 AA) et sur les ajouts des WCAG 2.2 AA. C'est une liste de travail, pas un certificat.

- [ ] **Clavier** : toutes les fonctions utilisables sans souris, pas de piège au clavier (WCAG 2.1.1, 2.1.2) ; ordre de focus logique (2.4.3) ; focus visible (2.4.7) et non masqué par des barres fixes (2.4.11, WCAG 2.2).
- [ ] **Contraste** : texte >= 4,5:1, grand texte et composants d'interface >= 3:1 (1.4.3, 1.4.11) ; respect du mode couleurs forcées et du mode sombre ; aucune information donnée par la couleur seule (1.4.1).
- [ ] **Zoom et reflow** : texte agrandissable à 200 % sans perte (1.4.4) ; reflow à 320 px CSS / zoom 400 % sans défilement dans deux directions (1.4.10) ; surcharge de l'espacement du texte acceptée (1.4.12) ; unités relatives.
- [ ] **Nouvelles réponses annoncées** : le conteneur des réponses du tuteur est une région `aria-live="polite"` (ou `role="log"`) pour qu'un lecteur d'écran annonce une nouvelle réponse sans déplacer le focus (4.1.3) ; ne déplacer le focus que sur action explicite.
- [ ] **Étiquettes et structure** : chaque champ a une étiquette et une consigne programmatiques (1.3.1, 3.3.2, 4.1.2) ; titres et repères ; les listes sont de vraies listes ; les lignes d'étapes produites par `adapt` deviennent de vrais éléments de liste.
- [ ] **Aucune limite de temps** : pas de réponse chronométrée, pas de compte à rebours, pas de déconnexion automatique (2.2.1), en cohérence avec le profil `sans_pression_temps` ; progression sauvegardée.
- [ ] **Mouvement** : aucune animation essentielle ; respecter `prefers-reduced-motion` ; rien ne clignote plus de 3 fois par seconde (2.3.1, 2.3.3).
- [ ] **Contrôles de la sortie vocale** : lecture, pause, arrêt, vitesse et choix de la voix pour toute réponse synthétisée, pas de lecture automatique (1.4.2) ; la sortie vocale est facultative et indépendante du lecteur d'écran ; lire `AdaptedReply.spoken`, pas le texte brut.
- [ ] **Langue** : attribut `lang` sur la page et sur les passages dans une autre langue (3.1.1, 3.1.2) pour que la synthèse choisisse la bonne voix.
- [ ] **Rendu des maths** : afficher `mathml` nativement ou avec une bibliothèque qui préserve l'accessibilité ; conserver `alttext` ; proposer une option « afficher en texte » ; ne pas rendre les maths en image sans alternative textuelle (1.1.1).
- [ ] **Cibles et saisie** : cibles de pointage d'au moins 24x24 px CSS (2.5.8), aucune action uniquement au glisser-déposer (2.5.7), pas de ressaisie redondante (3.3.7), pas d'authentification par test cognitif (3.3.8) ; proposer des choix et des réponses courtes pour la motricité ; ne pas bloquer le collage ni la dictée vocale.
- [ ] **Préférences** : sélecteur de profil utilisable par l'élève, un parent ou l'enseignant ; conservé dans le stockage local de l'appareil seulement ; aucun compte ni copie serveur nécessaire ; aucune déduction à partir du comportement ; choix modifiable ou supprimable à tout moment.
- [ ] **Cohérence et aide** : navigation et aide à des emplacements cohérents (3.2.3, 3.2.6) ; messages d'erreur en texte, reliés au champ.
- [ ] **Audit** : un audit RGAA 4.1 avec de vraies technologies d'assistance (NVDA, JAWS, VoiceOver, TalkBack ; clavier seul ; zoom 400 % ; mode contraste élevé) avant toute affirmation de conformité, et une déclaration d'accessibilité publiée lorsque la réglementation française l'exige.

## 6. Limites assumées

* Aucune affirmation de conformité au RGAA, aux WCAG ou à EN 301 549. C'est une couche de texte et une liste de contrôle.
* **Braille** : non produit ici. Les utilisateurs de plage braille s'appuient sur leur lecteur d'écran et sur des outils externes de braille mathématique (par exemple le projet « MathsDV » de l'apiDV) ; nous fournissons seulement du MathML et une forme parlée que ces outils peuvent exploiter. Les codes de braille mathématique (Nemeth, UEB, braille mathématique français) sont hors périmètre.
* **Langue des signes française (LSF)** : non couverte.
* **Saisie manuscrite / dysgraphie** : non couverte (ni stylet, ni reconnaissance d'écriture). Le profil de motricité ne fait que réduire la quantité de saisie demandée.
* **Contenu image** (figures, graphiques) : le module ne décrit pas les images. Toute figure utilisée par le tuteur nécessite une description textuelle rédigée par un humain ou par une chaîne de production validée.
* **Voix** : la forme parlée vise le français et l'anglais ; la prononciation du texte par la synthèse, la qualité et la vitesse de la voix relèvent de l'intégrateur. Nous n'avons pas testé tous les lecteurs d'écran ni toutes les synthèses.
* **Dates et ordinaux** : seulement les formes courantes ; le format anglais `jj/mm/aaaa` est lu chiffre par chiffre avec « slash », car il est ambigu.
* Les lexiques d'idiomes, de pression de temps et d'indices sont finis. Un contrôle réussi ne prouve pas qu'une réponse est facile à comprendre ; un contrôle en échec invite à reformuler, il ne tranche pas.
* Le découpage des phrases est volontairement prudent : il peut laisser une phrase plus longue que la limite plutôt que risquer d'en altérer le sens.
* Les profils sont des valeurs par défaut choisies par nous ; ils n'ont pas encore été validés avec des élèves ni par des experts de l'accessibilité (section 7). Les seuils numériques (12, 14, 15, 18, 20 mots) sont des points de départ, pas des résultats.
* Pas de prise en charge d'autres langues que le français et l'anglais.

## 7. Comment chercheurs et experts de l'accessibilité peuvent aider à évaluer ce travail

Les seuils chiffrés, les lexiques et les ensembles de préférences sont des hypothèses. Voici un protocole pour les mettre à l'épreuve :

1. **Échantillon.** Produire un échantillon fixe de réponses du tuteur par profil (par exemple 30 par profil, stratifié : indice à 3 niveaux, retour sur erreur, encouragement, réponses contenant fractions, puissances, racines, unités, inéquations). Utiliser les mêmes entrées avec et sans `profile_prompt_addendum`, avec et sans `adapt`, pour séparer l'effet de chacun. Publier l'échantillon au format de corpus ci-dessous.
2. **Annotation par des experts.** Des annotateurs compétents (auditeurs d'accessibilité, enseignants spécialisés, orthophonistes, ergothérapeutes, transcripteurs braille, utilisateurs de lecteurs d'écran, enseignants de mathématiques) évaluent chaque réponse indépendamment, sans connaître la condition. Pour chaque code de `lint`, ils indiquent présent / absent ; pour chaque profil, ils donnent une note globale d'utilisabilité (de 1 à 5) et un commentaire libre. Utiliser le même schéma JSONL que `corpus-access/accessibility-cases.jsonl` (`id, profile, lang, input, expect_codes, expect_absent_codes, spoken_expected, note`) : les annotateurs renseignent `expect_codes` et `expect_absent_codes`, de sorte que leur production est directement un fichier de tests.
3. **Accord inter-annotateurs.** Au moins 3 annotateurs par élément ; rapporter le kappa de Fleiss ou l'alpha de Krippendorff par code (kappa de Cohen pour deux annotateurs), avec intervalles de confiance, et examiner les désaccords pour affiner les définitions. Un élément sous le seuil convenu (par exemple kappa < 0,6) signale une règle ambiguë, à reformuler avant de s'y fier. Mesurer aussi l'accord de `lint` avec la majorité des experts (précision et rappel par code) ; faux positifs et faux négatifs deviennent de nouveaux cas de corpus et des modifications de lexique.
4. **Maths parlées.** Faire passer les sorties de `spoken_math` dans les synthèses et lecteurs d'écran réellement utilisés (NVDA, JAWS, VoiceOver), demander à des utilisateurs de lecteurs d'écran de noter ce qu'ils ont entendu (dictée) et de répondre à une question de compréhension. Mesurer la restitution exacte de l'expression. Comparer les styles de fractions `explicit` et `natural` et les annonces de parenthèses.
5. **Études auprès d'élèves.** Uniquement avec avis éthique, consentement parental et accord de l'établissement, et sans recueillir de diagnostic : recruter par *préférence* (par exemple « utilise un lecteur d'écran », « préfère les phrases courtes ») via des associations ou des établissements, pas par étiquette médicale. Comparer compréhension, temps de réalisation et effort perçu avec et sans le profil. Ne jamais journaliser les messages des élèves à cette fin sans consentement explicite.
6. **Publication.** Publier le guide d'annotation, les notes brutes, les statistiques d'accord et la version (commit git) de ce module, et dire clairement ce qui a été testé ou non. Les contributions (cas de corpus, entrées de lexique, corrections de formes parlées, nouveaux besoins) sont les bienvenues en pull request ; chacune doit s'accompagner d'au moins un test.
