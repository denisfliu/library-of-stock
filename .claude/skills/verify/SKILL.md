---
name: verify
description: Verify a pipeline or renderer change end-to-end — rebuild, validate, and spot-check an affected page.
---

# Verify a change

Run this after any change to `lib/`, `dev/`, or analysis/cards JSON before declaring work done.

## Step 1: Build

```bash
./build.sh
```

Must end with `Done.` and no traceback. If the change touched a renderer or `lib/common.py`/`lib/render/theme.py`, run `./build.sh --force` instead so every page re-renders through the changed code.

## Step 2: Validate

```bash
python lib/validate.py
```

Compare against the known-baseline issues (currently: `NEEDS_ABC_REVIEW` items and topics awaiting cards). **Any new issue category or count increase means the change broke something** — investigate before proceeding.

## Step 3: Spot-check the affected surface

Don't stop at exit codes — confirm the actual behavior:

- **Renderer change**: `git diff --stat -- output index.html` and inspect one changed page's diff. The diff must contain only what the change intends (e.g., a CSS rule) — unexplained content changes mean a bug. Grep the rendered HTML for the new/changed markup.
- **Pipeline change (fetch/parse/run)**: run a real fetch into the scratch area and check the output header:
  ```bash
  python lib/run.py "Smetana" "7,8,9,10" --outdir /tmp/verify_check
  ```
- **Queue/batch change**: `python lib/queues/batch_worker.py status` and `python lib/queues/topic_queue.py summary` must both run clean.
- **Data migration**: write a small assertion script over all `output/*/analysis.json` (and `cards.json`) proving the invariant (e.g., "no file still has key X"), not just a sample.

## Step 4: Report

State what was rebuilt, the validation delta (should be "no new issues"), and what the spot-check showed — with the concrete evidence (diff excerpt, grep hit), not just "it works".
