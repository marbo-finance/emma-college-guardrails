# Accessibility layer (`emma_college.access`)

Emma Collège is a pedagogical guardrail layer for an AI math tutor (French collège, 4e/3e, ages 13-15). This module makes the tutor's *text* easier to use for pupils with different access needs, without weakening the pedagogical contract. It is deterministic, stdlib-only, Apache 2.0.

> **Status: work in progress, not an accessibility certification.** Nothing here claims RGAA, WCAG or EN 301 549 compliance. The module checks and transforms text; compliance can only be established by auditing the whole interface (see section 5 and 6).

French version: [ACCESSIBILITE.md](ACCESSIBILITE.md).

## 1. Stance (the design principles)

1. **Needs-based preference profiles, not diagnoses.** Health and disability data is a special category under GDPR art. 9. The system never asks for a diagnosis, never stores one, and never infers one from what the pupil writes: no profiling of the child. A *profile* is a named bundle of presentation preferences (`lecture_vocale`, `texte_aere`, `une_etape_a_la_fois`, `langage_litteral`, `sans_pression_temps`, `contraste_zoom`...) **chosen by the pupil, a parent or a teacher** and **stored locally (on the device) by the integrator**. Profile names are French identifiers for a *need* or a *preference*. A profile object contains no free-text field and no pupil data. Several profiles can be combined (`combine_profiles`), and the strictest limit wins.
2. **Accessibility never weakens the pedagogical contract.** Hints, not answers, still applies. `profile_prompt_addendum()` repeats it in every non-default addendum, and `adapt()` only changes form (whitespace, line breaks, sentence boundaries, emoji), never mathematical content: it never alters a digit and never adds a numeric value (tested). An adapted reply must still pass the leak check; that check lives in another module (`emma_college/leak.py`), so run it on `AdaptedReply.text` (and on `.spoken` if you speak it) as the last step.
3. **The deterministic layer handles text only.** It can lint and transform a reply. Focus order, contrast, keyboard operation, ARIA, zoom and reflow belong to the integrating interface and to its RGAA 4.1 / WCAG 2.2 AA audit. Section 5 lists what the demo UI must do.
4. **Honest limits.** Section 6 lists what is not covered. In particular, Braille output is delegated to screen readers and external tools (for example the apiDV "MathsDV" project), there is no sign-language support, and no handwriting-input support (dysgraphia).

## 2. Profiles

A profile is a frozen dataclass: `name, label_fr, label_en, needs, max_sentence_words, max_steps_per_reply, forbid_figurative, forbid_time_pressure, spoken_math, limit_symbols, limit_emoji`. `PROFILES` maps names to profiles. The "needs" are presentation needs (vocabulary in `NEEDS`), not conditions.

| Profile | Presentation need(s) it supports | Typical use | What the layer checks (`lint`) and adapts (`adapt`) |
|---|---|---|---|
| `default` | none | no adaptation | universal checks only: colour-only references, ALL CAPS, very long paragraphs |
| `lecture_vocale` | `lecture_ecran`, `acces_audio` | pupil who reads through a screen reader, braille display or speech output (blind or low vision) | sentences <= 20 words, <= 3 steps, no emoji, no arrows/ASCII art/tables, no visual-only pointers, raw LaTeX flagged; `adapt` produces a spoken form and MathML |
| `contraste_zoom` | `vision_reduite`, `agrandissement` | pupil who needs high contrast and zoom (200 %-400 %) | sentences <= 18 words, <= 3 steps, <= 1 emoji, no unexplained symbols, visual-only pointers flagged (info) |
| `texte_aere` | `lecture_fluente` | pupil for whom dense text is tiring to read | sentences <= 14 words, <= 3 steps, <= 2 emoji; `adapt` splits long sentences at safe conjunctions, one step per line |
| `nombres_clairs` | `nombres_symboles`, `charge_cognitive` | pupil who needs numbers and symbols read out clearly, few things at once | sentences <= 15 words, <= 2 steps/questions, <= 1 emoji, no unexplained symbols; spoken form and MathML |
| `une_etape_a_la_fois` | `attention_soutenue`, `charge_cognitive` | pupil who works best with one thing at a time | sentences <= 12 words, **one** step and one question per reply, no time pressure, <= 1 emoji |
| `langage_litteral` | `langage_litteral`, `previsibilite` | pupil who needs literal language and a predictable structure | no figurative expression or idiom, no time pressure, no emoji, sentences <= 15 words; the addendum asks for the same structure in every message |
| `sans_pression_temps` | `rythme_personnel`, `previsibilite` | pupil who needs to work at their own pace | no time-pressure wording ("vite", "chrono", "en moins de", "hurry"...) |
| `texte_prioritaire` | `texte_prioritaire` | pupil for whom sound is not reliable | no audio-only cue ("écoute", "comme j'ai dit"), information always written, sentences <= 18 words |
| `reponses_courtes` | `motricite_fine` | pupil for whom typing is slow or tiring | no typing-heavy requests ("rédige un paragraphe", "recopie"), <= 2 steps, answers as a number, a word or a choice |

Profiles are listed by need and preference on purpose. We do not claim that a given need maps to a given condition (many pupils with the same condition have different needs, and many pupils without a diagnosis share the same needs).

### Lint codes

| Code | Severity | Meaning |
|---|---|---|
| `LONG_SENTENCE` | warn | more words than the profile allows |
| `TOO_MANY_STEPS`, `TOO_MANY_QUESTIONS` | warn | more numbered/labelled steps or questions than allowed in one reply |
| `FIGURATIVE` | warn | idiom or figurative expression (about 70 French and 40 English phrases, including variants, in `access_data/lexicons.json`) |
| `TIME_PRESSURE` | warn | urgency wording, with a simple negation guard ("pas besoin d'aller vite" is accepted) |
| `SYMBOL_UNEXPLAINED` | warn | arrows, `≈`, `∴`, geometric shapes, ASCII arrows that screen readers read badly |
| `ASCII_ART`, `TABLE` | warn | box drawing, separator lines, character drawings, text tables |
| `EMOJI_EXCESS` | warn | more emoji than the profile allows |
| `COLOR_ONLY` | warn | colour-only reference ("la case rouge"); all profiles |
| `VISUAL_DEIXIS` | warn / info | "comme tu peux le voir", "ci-dessus", "à gauche" (warn for screen-reader profiles, info for low vision) |
| `AUDIO_ONLY_CUE` | warn | "écoute bien", "comme j'ai dit" (text-first profile) |
| `CAPS_SHOUTING` | info | ALL CAPS word (acronyms and point names such as `ABCD` excepted); all profiles |
| `LONG_PARAGRAPH` | info | very long unbroken paragraph; all profiles |
| `RAW_LATEX` | warn | LaTeX left unrendered in a speech profile |
| `TYPING_HEAVY` | warn | request for long typed answers (motor profile) |

The lexicons are plain JSON and meant to be extended by pull request; every new entry should come with a corpus case.

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

* `lint` is deterministic and profile-driven; `lang` selects the idiom/cue lexicon.
* `adapt` is conservative: it removes emoji beyond the profile limit, puts numbered steps on their own line, splits an over-long sentence only at a safe conjunction (`, mais`, `, puis`, `, donc`, `, car`, `;`... never inside parentheses or an enumeration), and for speech profiles produces `spoken` and `mathml`. `findings` holds the remaining lint findings on the adapted text followed by `ADAPT_*` audit entries (what was changed). It does **not** rewrite idioms or time pressure: it reports them, so the integrator can ask the LLM to regenerate with the addendum.
* `to_mathml` accepts a safe subset (numbers, identifiers, `+ − × ÷ =`, inequalities, `\frac`, `a/b` between simple operands, superscripts, subscripts, `\sqrt`, parentheses, units, degrees). It never uses `eval`, escapes all text, and raises `ValueError` outside the subset. The `alttext` attribute carries the spoken form.
* Integrator decision: keep `$...$` in `AdaptedReply.text` and substitute the `mathml` items in order when rendering (MathML support in assistive technology varies, so keep the `alttext`), or speak `spoken` directly.

## 4. Spoken math

Default style is explicit and unambiguous (`trois sur quatre`); `style="natural"` gives `un demi`, `un tiers`, `deux tiers`, `un quart`, `trois quarts` only for those fractions. Negative numbers are `moins sept`; ambiguous parentheses are announced (`parenthèse ouverte ... parenthèse fermée`); a complex fraction is announced with numerator and denominator so that nothing depends on reading order. French numbers up to 999 999 999 follow the 70/80/90 rules (`soixante et onze`, `quatre-vingts` / `quatre-vingt-un`, `deux cents` / `deux cent un`, `et un`, `cent` agreement) and unit agreement (`1,5 kg` is singular, `21 min` is `vingt et une minutes`).

| Input | French | English |
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

Known conventions and traps (all in the tests): a decimal point or comma is always a decimal separator (`1,2,3` is read as one decimal then `3`); an unspaced single-letter unit (`3t`, `2m`) is read as a variable, so a unit like `m`, `g`, `t`, `s`, `l` needs a space after the number; an unspaced hyphen between two digits is read as a minus (`10-15` is `dix moins quinze`), so ranges should be written in words; the system prompt asks the model to write the minus sign as `−` with spaces. Numbers above 999 999 999 are read digit by digit.

## 5. What the integrating interface must provide

The module cannot provide these. They are the checklist for the demo UI and for any integrator, aligned with RGAA 4.1 (which is based on WCAG 2.1 AA) and the WCAG 2.2 AA additions. It is a work list, not a certificate.

- [ ] **Keyboard**: every function usable without a mouse, no keyboard trap (WCAG 2.1.1, 2.1.2); logical focus order (2.4.3); visible focus (2.4.7) that is not hidden by sticky bars (2.4.11, WCAG 2.2).
- [ ] **Contrast**: text >= 4.5:1, large text and interface components >= 3:1 (1.4.3, 1.4.11); respect forced-colors and dark mode; never information by colour alone (1.4.1).
- [ ] **Zoom and reflow**: text enlargeable to 200 % without loss (1.4.4); reflow at 320 CSS px / 400 % zoom with no two-dimensional scrolling (1.4.10); text spacing overrides supported (1.4.12); relative units.
- [ ] **New replies announced**: the tutor's reply container is an `aria-live="polite"` region (or `role="log"`), so a screen reader announces a new reply without moving focus (4.1.3); move focus only on explicit user action.
- [ ] **Labels and structure**: every field has a programmatic label and instruction (1.3.1, 3.3.2, 4.1.2); headings and landmarks; lists are real lists; the "step" lines produced by `adapt` become real list items.
- [ ] **No time limits**: no timed answers, no countdown, no auto-timeout (2.2.1); consistent with the `sans_pression_temps` profile; progress saved.
- [ ] **Motion**: no essential animation; honour `prefers-reduced-motion`; nothing flashes more than 3 times per second (2.3.1, 2.3.3).
- [ ] **Speech output controls**: play, pause, stop, speed and voice choice for any synthesised reply, no autoplay (1.4.2); the speech output must be optional and independent of the screen reader; play `AdaptedReply.spoken`, not the raw text.
- [ ] **Language**: `lang` attribute on the page and on parts in another language (3.1.1, 3.1.2) so that TTS picks the right voice.
- [ ] **Math rendering**: render `mathml` natively or with a library that keeps accessible math; keep `alttext`; offer a "show as text" toggle; do not render maths as images without a text alternative (1.1.1).
- [ ] **Targets and input**: pointer targets >= 24x24 CSS px (2.5.8), no dragging-only action (2.5.7), no redundant re-entry (3.3.7), no cognitive-test login (3.3.8); offer choices and short answers for motor needs; do not block paste or voice dictation.
- [ ] **Preferences**: profile picker usable by the pupil, a parent or a teacher; stored in local storage on the device only; no account or server copy required; no inference from behaviour; the choice can be changed or deleted at any time.
- [ ] **Consistency and help**: consistent navigation and help placement (3.2.3, 3.2.6); error messages in text, linked to the field.
- [ ] **Audit**: an RGAA 4.1 audit with real assistive technology (NVDA, JAWS, VoiceOver, TalkBack; keyboard only; 400 % zoom; high-contrast mode) before any claim of compliance, and a published accessibility statement (déclaration d'accessibilité) as required in France for covered bodies.

## 6. Honest limits

* No claim of RGAA, WCAG or EN 301 549 compliance. This is a text layer plus a checklist.
* **Braille**: not produced here. Braille display users rely on their screen reader and on external math-braille tooling (for example the apiDV "MathsDV" project); we only provide MathML and a spoken form that such tools can consume. Nemeth/UEB/French math-braille codes are out of scope.
* **Sign language** (LSF): not covered.
* **Handwriting / dysgraphia input**: not covered (no pen input, no handwriting recognition). The motor profile only reduces typing demand.
* **Image content** (figures, graphs): the module does not describe images. Any figure used by the tutor needs a text description authored by a human or a vetted pipeline.
* **Speech**: the spoken form targets French and English; TTS pronunciation of the resulting text, voice quality and speed are the integrator's responsibility. We have not tested with every TTS or screen reader.
* **Dates and ordinals** are handled only in common forms; English `dd/mm/yyyy` is read digit by digit with "slash" because it is ambiguous.
* The idiom, time-pressure and cue lexicons are finite. A passing lint is not proof that a reply is easy to understand; a failing one is a prompt for rewrite, not a verdict.
* Sentence splitting is conservative on purpose: it may leave a sentence longer than the limit rather than risk altering the meaning.
* Profiles are defaults chosen by us; they have not been validated with pupils or by accessibility experts yet (see section 7). Numeric limits (12, 14, 15, 18, 20 words) are starting points, not findings.
* No multi-lingual support beyond French and English.

## 7. How researchers and accessibility experts can help evaluate this

The numeric limits, lexicons and profile bundles are hypotheses. A protocol that lets them be tested:

1. **Sample.** Generate a fixed sample of tutor replies per profile (for example 30 per profile, stratified: hint at 3 levels, error feedback, encouragement, replies with fractions, powers, roots, units, inequalities). Use the same inputs with and without `profile_prompt_addendum` and with and without `adapt`, so the effect of each is separable. Publish the sample in the corpus format below.
2. **Expert annotation.** Annotators with relevant expertise (accessibility auditors, teachers specialised in inclusive education, speech-language therapists, occupational therapists, braille transcribers, screen-reader users, math teachers) rate each reply independently, blind to the condition. For each lint code they mark present / absent, and for each profile they give an overall usability rating (1-5) with a free comment. Use the same JSONL schema as `corpus-access/accessibility-cases.jsonl` (`id, profile, lang, input, expect_codes, expect_absent_codes, spoken_expected, note`): annotators supply `expect_codes` and `expect_absent_codes`, so their output is directly a test file.
3. **Inter-rater agreement.** At least 3 raters per item; report Fleiss' kappa or Krippendorff's alpha per code (Cohen's kappa for two raters), with confidence intervals, and review the disagreements to refine the code definitions. Items below the agreed threshold (for example kappa < 0.6) mean the rule is ambiguous and should be reworded before being relied upon. Measure also the agreement of the automatic `lint` with the expert majority (precision and recall per code); false positives and false negatives become new corpus cases and lexicon edits.
4. **Spoken math.** Run `spoken_math` outputs through the TTS and screen readers actually used (NVDA, JAWS, VoiceOver) and ask screen-reader users to write down what they heard (dictation task) and to answer a comprehension question. Score exact recovery of the expression. Compare `explicit` and `natural` fraction styles and the parenthesis announcements.
5. **Pupil studies.** Only with ethics review, parental consent and the school's agreement, and without collecting diagnoses: recruit through associations or schools by *preference* (for example "uses a screen reader", "prefers short sentences"), not by medical label. Compare comprehension, time on task and self-reported effort with and without the profile. Never log pupil messages for this purpose without explicit consent.
6. **Reporting.** Publish the annotation guide, raw ratings, the agreement statistics and the version (git commit) of this module, and state clearly what was and was not tested. Contributions (corpus cases, lexicon entries, corrections to spoken forms, new needs) are welcome as pull requests; each must come with at least one test.
