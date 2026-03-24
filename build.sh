#!/bin/bash
# Run all renderers. Use after any batch or manual analysis.
# Default: incremental (skips unchanged files).
# Pass --force to re-render everything.
set -e

FORCE=""
if [[ "$*" == *"--force"* ]]; then
    FORCE="--force"
fi

python3 lib/rerender.py $FORCE
python3 lib/render/render_cards.py $FORCE
python3 lib/render/render_questions.py $FORCE
python3 lib/render/render_audio.py $FORCE
python3 lib/render/render_score_review.py
python3 lib/build_index.py
python3 lib/validate.py
echo "Done."
