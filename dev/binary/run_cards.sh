#!/bin/bash
set -e
export PATH="$LOCALAPPDATA/Programs/Python/Python312:$PATH" PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
cd "$(dirname "$0")"
run() {  # scope topic name slug
  python topic.py "$2" --name "$3" > /dev/null
  BINARY_OUT_SUB=clauses_$1 python topic.py "$2" --name "$3" > /dev/null
  python cards.py "$4" --scope "$1" --title "$3" | head -1
}
run literature "fyodor dostoevsky" "Fyodor Dostoevsky" fyodor_dostoevsky
run literature "toni morrison" "Toni Morrison" toni_morrison
run literature "clarice lispector" "Clarice Lispector" clarice_lispector
run music "bela bartok" "Béla Bartók" bela_bartok
run music "johann sebastian bach" "J. S. Bach" j_s_bach
run music "sofia gubaidulina" "Sofia Gubaidulina" sofia_gubaidulina
echo CARDS DONE
