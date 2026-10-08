#!/bin/bash
# Contrôle avant push public. Usage : leak-gate.sh <plage-de-commits>
# Liste de regex tenue HORS du dépôt : EMMA_LEAK_DENYLIST, par défaut ~/.emma/leak-denylist.txt.
# Sortie : 0 = propre, 1 = terme trouvé, 2 = erreur (jamais masquée).
set -u
EMMA_LEAK_DENYLIST="${EMMA_LEAK_DENYLIST:-$HOME/.emma/leak-denylist.txt}"
[ -f "$EMMA_LEAK_DENYLIST" ] || { echo "leak-gate: liste introuvable ($EMMA_LEAK_DENYLIST)"; exit 2; }
RANGE="${1:?leak-gate: plage de commits requise}"
ROOT=$(git rev-parse --show-toplevel) || exit 2
cd "$ROOT" || exit 2
BUILTIN='sk-[A-Za-z0-9]{20,}|emma_[A-Za-z0-9_]{20,}|192\.168\.[0-9]+\.[0-9]+|100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.[0-9]+\.[0-9]+|AKIA[0-9A-Z]{16}'
TMP=$(mktemp) || exit 2
trap 'rm -f "$TMP" "$TMP.add" "$TMP.hits" "$TMP.log" "$TMP.plus"' EXIT
FAIL=0
# 1) Ajouts de tous les commits à pousser (merges inclus)
git log -p -m --format= $RANGE > "$TMP.log" || { echo "leak-gate: git log en erreur"; exit 2; }
# Chaque grep vérifié séparément : une erreur n'est jamais masquée par l'étape suivante
grep '^+' "$TMP.log" > "$TMP.plus"; rc=$?
[ $rc -le 1 ] || { echo "leak-gate: erreur grep (ajouts)"; exit 2; }
grep -v '^+++' "$TMP.plus" > "$TMP.add"; rc=$?
[ $rc -le 1 ] || { echo "leak-gate: erreur grep (filtre ajouts)"; exit 2; }
grep -n -I -E -f "$EMMA_LEAK_DENYLIST" -e "$BUILTIN" "$TMP.add" > "$TMP.hits"; rc=$?
if [ $rc -eq 0 ]; then echo "LEAK-GATE (commits $RANGE) :"; head -c 2000 "$TMP.hits"; FAIL=1
elif [ $rc -gt 1 ]; then echo "leak-gate: erreur grep (commits)"; exit 2; fi
# 2) État suivi courant
git grep -n -I -E -f "$EMMA_LEAK_DENYLIST" -e "$BUILTIN" -- . > "$TMP.hits"; rc=$?
if [ $rc -eq 0 ]; then echo "LEAK-GATE (fichiers suivis) :"; head -c 2000 "$TMP.hits"; FAIL=1
elif [ $rc -gt 1 ]; then echo "leak-gate: erreur git grep"; exit 2; fi
[ "$FAIL" = 0 ] && { echo "leak-gate: OK ($RANGE)"; exit 0; }
echo "leak-gate: BLOQUÉ"; exit 1
