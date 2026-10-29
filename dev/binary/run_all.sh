#!/bin/bash
# Full rebuild after answerlines.py / links.py changes, plus every scope's
# key and clause tiers, then the browser. New scopes are embedded once
# (build_clauses); existing ones are only relabelled.
set -e
export PATH="$LOCALAPPDATA/Programs/Python/Python312:$PATH" PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
cd "$(dirname "$0")"
python build_units.py
python answerlines.py | grep "^units"
python links.py | grep -v "^  "
python binaries.py | tail -2
for s in music literature extra history csmath; do python keys.py --scope $s --lower | tail -1; done
for s in music literature extra history csmath; do
  if [ -f out/clauses_$s/vecs.npy ]; then
    python build_clauses.py --scope $s --relabel
  else
    python build_clauses.py --scope $s 2>&1 | grep -v "Batches\|Loading\|HF_TOKEN"
    cp out/clauses_music/thresholds.json out/clauses_$s/thresholds.json
    BINARY_OUT_SUB=clauses_$s python anchors.py
    NQ=$(python -c "import pickle;print(int(pickle.load(open('out/clauses_$s/units.pkl','rb'))['query'].sum()))")
    BINARY_OUT_SUB=clauses_$s python sweep.py --queries "$NQ" | tail -1
  fi
  BINARY_OUT_SUB=clauses_$s python binaries.py | tail -1
  python corpus_cards.py --scope $s | tail -1
done
python browse.py --standalone | tail -1
echo ALL BUILT
