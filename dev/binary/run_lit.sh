#!/bin/bash
# Rebuild after answerlines.py changed, then build the literature tiers.
set -e
export PATH="$LOCALAPPDATA/Programs/Python/Python312:$PATH" PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
cd "$(dirname "$0")"
python links.py | grep -v "^  "
python binaries.py | tail -3
python keys.py --scope music --lower | tail -1
python keys.py --scope literature --lower | tail -1
python build_clauses.py --scope music --relabel
BINARY_OUT_SUB=clauses_music python binaries.py | tail -2
python build_clauses.py --scope literature 2>&1 | grep -v "Batches\|Loading\|HF_TOKEN"
cp out/clauses_music/thresholds.json out/clauses_literature/thresholds.json
NQ=$(python -c "import pickle;print(int(pickle.load(open('out/clauses_literature/units.pkl','rb'))['query'].sum()))")
echo "literature clauses: $NQ"
BINARY_OUT_SUB=clauses_literature python anchors.py
BINARY_OUT_SUB=clauses_literature python sweep.py --queries "$NQ" | tail -1
BINARY_OUT_SUB=clauses_literature python binaries.py | tail -2
echo ALL DONE
