# Binary clue detection (proof of concept, Oct 2026)

A **binary** is a clue that points to exactly one answerline across the
whole corpus. This directory finds them corpus-wide. It uses the stored
Qwen3 sentence and bonus-part vectors (`mirror/embeddings.sqlite`) and makes
no model calls after calibration.

Run in order from `dev/binary/`; outputs go to `out/` (git-ignored):

| step | script | time |
|---|---|---|
| clue units + vectors | `build_units.py` | ~1 min |
| canonical answerlines (+ answer kinds) | `answerlines.py` | ~1 min |
| exact all-pairs top-64 neighbours (GPU) | `sweep.py` | ~4 min |
| rare-term ("anchor") index | `anchors.py` | ~1 min |
| which answerlines each question names; label links | `links.py` | ~2.5 min |
| the binary test | `binaries.py` | ~1.5 min |
| per-topic report | `topic.py "bela bartok"` / `topic.py odin --seed norse --name "Norse mythology"` | ~1 min |
| **Tier A: key phrases** (title / movement / nickname → work → creator) | `keys.py --scope music --lower [--explain "phrase" ...]` | ~1.4 min |
| key-phrase report | `keys_report.py --scope music "bela bartok" ...` | seconds |

**Tier B: clauses** (music). Run in order:
1. `clauses.py --selftest`, then `build_clauses.py --scope music` (~4 min, embeds 110k clauses).
2. With `BINARY_OUT_SUB=clauses_music` set, run `anchors.py`, `sweep.py --queries 110569`
   (20 s), `binaries.py` and `topic.py`.

The universe holds the music clauses plus every other corpus sentence, so outside-music
conflicts stay visible. Clauses that don't refer to the answer are context. The clause
tier uses its own calibrated thresholds from `out/clauses_music/thresholds.json`
(`calib.py` run with the same `BINARY_OUT_SUB`). The sentence thresholds were only 62%
precise on clauses.

**Rebuild**: `run_all.sh` rebuilds everything:
- units, answerlines, links and sentence binaries;
- for each scope: keys, then clause tier (embedded once; afterwards only relabelled) and
  corpus cards;
- finally the browser.

**Scopes** (together, the whole corpus): `music`, `literature`, `extra` (myth, religion,
philosophy, social science, biology), `history`, `csmath`, all with a clause tier; `arts`
(visual and other fine arts), `science` (physics, chemistry, other science), `geography`,
`misc` (current events, other academic) and `pop`, keys only. Without a clause universe,
`corpus_cards.py` skips the clause tier. `run_cards_all.sh` rebuilds keys and cards for
every scope.

Canonicalization also merges vector-checked variants (centroid cosine ≥ 0.93 for middle
names, ≥ 0.90 for "parable/legend of X"). Lowercase keys that are cut off mid-phrase are
dropped.
- `run_lit.sh`: the full rebuild after `answerlines.py` changes. It reruns `links.py` and
  the sentence binaries, the keys for both scopes, relabels the music clauses, then builds
  the literature clause tier. It takes about 25 min, mostly embedding.
- `run_cards.sh`: renders the six example decks.
- Each card records the set difficulties it has appeared at; the deck page filters on
  them (any / 7+ / 8+ / 9+).

**Binaries browser**: `corpus_cards.py --scope <scope>` builds every answerline's
deck in one vectorised pass (about 30 s per scope). Then `browse.py [--standalone]` writes
`out/browse/`:
- one page in the study-page clue-table style;
- `data/index.json`, which holds qbreader's taxonomy, then names, category /
  subcategory / alternate, key phrases and two ints per card (tiers, difficulties and
  question type; set years), so the filters never need card text;
- about 1.5 MB card shards, fetched on demand.

Search covers answers, key phrases and clue text. The filters follow qbreader:
category → subcategory → alternate subcategory, difficulties 1–10, a year range and
tossups / bonuses. Confirming tiers can also be filtered. Tested end to end in Chrome over `python -m http.server`.

Answerlines nest: works under their creator, characters under their work
(`keys.ParentRule`), and each clue under the creator's work its questions
point to (the card's `u`).

**Publishing** (the site's Binaries page): `browse.py --upload` uploads
`out/browse/data/` to R2 under `binaries/<content hash>/` and writes the repo
root `binaries.html` pointing at it. Commit that page; CI deploys it as is,
since the corpus behind the data is local-only.

**Card view**: `cards.py <slug>` merges a topic's three tiers into one deck. It needs
`topic.py` for the same topic in both `out/` and `out/clauses_music/`, plus
`keys_music.json`.
- Clause binaries are the base cards.
- An overlapping sentence binary confirms a card; a sentence binary with no clause card
  becomes its own card.
- A key phrase joins the card it fits (the phrase is in the front, or in at least half
  the card's sentences); a key that fits nothing becomes its own card.

Tier A asks this for each key phrase: wherever the phrase appears and the hidden answer
is the same kind of thing, is that answer always this one, or one of its works? Each
question that contains the phrase counts as one of three things:
- **support**: the answer is the owner, or one of its works;
- **neutral**: the owner is named in that sentence, or the answer is a different kind of
  thing;
- **conflict**: a rival answer.

A key needs at least 2 support questions and an 80% share of support over conflicts.
`--explain` prints the full decision for any phrase.

"Names" means the capitalised, longest-match mention scan in `links.py`
(`mention_u.npz`). Bonus parts inherit the names in their lead-in.

Re-run `links.py` and everything after it whenever `answerlines.py` changes:
label ids are positional.

Calibration: `calib.py sample` → label the batches per `LABELING.md` →
`calib.py report`. Run `calib.py sample-low` to probe below the sweep's 0.70
floor. The current thresholds in `binaries.py` come from that run: 591 + 180
pairs labelled by model judges.

Each script's docstring explains its rules. The known gaps (clause-level
units, misspelled answerlines, fact conjunctions, single-question facts,
generic answerlines in topic discovery) are on the results page:
https://claude.ai/artifact/ELmAgu99aducxCSfnFZmr5
