# Golden render test

`run_golden.py` renders the frozen corpus in `fixtures/output/` through the
real renderers (stock, cards, questions, crossref index, sweep rematch,
overview) inside a temp sandbox, then diffs each artifact against the
snapshots in `expected/`. CI runs it before every deploy.

```bash
python tests/golden/run_golden.py            # verify; exit 1 on drift
python tests/golden/run_golden.py --update   # rebless after an intended change
```

When a renderer change fails the test: read the printed diff, and if the
change is intended, `--update` and commit the new snapshots in the same
commit as the renderer change — the snapshot diff doubles as a visual
review of what the change did to real pages.

## What the fixtures exercise

- `amos_tutuola`, `christopher_okigbo` — frozen copies of two real small
  topics (analysis + cards + question cache; no audio, no score clues, so
  no mtime-based cache busters can flap).
- `_categories/fixture_lit` — overview page with nesting, blurbs, a work
  entry, and an entry with no topic page (red-link/`no-page` path).
- `_sets/fixture_set` — sweep set hitting every matcher tier: exact,
  last-name alias, work alias, unmatched, and an alias blocked by the
  category gate.
- `topic_index.json` and the rematched `set.json` are snapshotted too;
  `report.json` is not (it embeds a generation date).

The sandbox is wired up via the `STOCK_ROOT` env override in `lib/common.py`
plus `cwd=sandbox` for the two scripts that still use cwd-relative paths.
Fixtures are deliberately frozen: they never track the live corpus, so a
real topic changing does not break the test.
