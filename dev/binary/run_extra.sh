#!/bin/bash
# Build the "extra" scope (mythology, religion, philosophy, social science, biology) end to end.
set -e
export PATH="$LOCALAPPDATA/Programs/Python/Python312:$PATH" PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
cd "$(dirname "$0")"
python keys.py --scope extra --lower | tail -1
python build_clauses.py --scope extra 2>&1 | grep -v "Batches\|Loading\|HF_TOKEN"
cp out/clauses_music/thresholds.json out/clauses_extra/thresholds.json
NQ=$(python -c "import pickle;print(int(pickle.load(open('out/clauses_extra/units.pkl','rb'))['query'].sum()))")
BINARY_OUT_SUB=clauses_extra python anchors.py
BINARY_OUT_SUB=clauses_extra python sweep.py --queries "$NQ" | tail -1
BINARY_OUT_SUB=clauses_extra python binaries.py | tail -2
python corpus_cards.py --scope extra | tail -1
python browse.py --standalone | tail -1
echo EXTRA DONE
