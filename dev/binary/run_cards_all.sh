#!/bin/bash
# Keys + corpus cards for every scope, then the browser (after a key/parent rule change).
set -e
export PATH="$LOCALAPPDATA/Programs/Python/Python312:$PATH" PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
cd "$(dirname "$0")"
SCOPES="music literature extra history csmath arts science geography misc pop"
for s in $SCOPES; do python keys.py --scope $s --lower | tail -1; done
for s in $SCOPES; do python corpus_cards.py --scope $s | tail -1; done
python browse.py --standalone | tail -1
echo CARDS BUILT
