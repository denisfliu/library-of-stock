#!/bin/bash
# Run all renderers. Use after any batch or manual analysis.
set -e
python3 lib/rerender.py
python3 lib/render_cards.py
python3 lib/render_questions.py
python3 lib/build_index.py
echo "Done."
