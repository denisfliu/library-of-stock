#!/bin/bash
# Run all renderers. Use after any batch or manual analysis.
# Default: incremental (skips unchanged files).
# Pass --force to re-render everything.
set -e

# Locate Python if it isn't on PATH (fresh Git Bash sessions on Windows).
if ! command -v python >/dev/null 2>&1 && [ -d "$LOCALAPPDATA/Programs/Python/Python312" ]; then
    export PATH="$LOCALAPPDATA/Programs/Python/Python312:$PATH"
fi

FORCE=""
if [[ "$*" == *"--force"* ]]; then
    FORCE="--force"
fi

# topic_index.json feeds link resolution in render.py, the sweep matcher,
# and overview red/blue links — rebuild it first (no-op write if unchanged).
python lib/crossref/crossref.py
python lib/rerender.py $FORCE
python lib/render/render_cards.py $FORCE
python lib/render/render_questions.py $FORCE
python lib/render/render_audio.py $FORCE
python lib/render/render_score_review.py
python dev/build_stats.py
python dev/build_changelog.py
python dev/build_crossrefs.py
# Sweep + overview pages: rematch flips red links blue as topics gain
# pages (no network); both must precede build_index.py, which reads
# their coverage stats for the explore strip.
python lib/sweep/build_set.py --all --rematch-only
python lib/render/build_overviews.py $FORCE
python lib/build_index.py
python lib/validate.py
echo "Done."
