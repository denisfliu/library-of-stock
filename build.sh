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

python lib/rerender.py $FORCE
python lib/render/render_cards.py $FORCE
python lib/render/render_questions.py $FORCE
python lib/render/render_audio.py $FORCE
python lib/render/render_score_review.py
python dev/build_stats.py
python dev/build_changelog.py
python dev/build_crossrefs.py
python lib/build_index.py
python lib/validate.py
echo "Done."
