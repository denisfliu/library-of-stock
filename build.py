"""build.py — single-process build orchestrator.

Runs every render/build stage in one process, parsing the corpus of
analysis JSONs exactly once. build.sh used to spawn ~10 processes that
each re-parsed all analyses; this hands the shared parse to every stage
via its ``analyses=`` parameter. Each stage module keeps its own CLI for
standalone use.

Stage order matters:
  - crossref first: render.py links, the sweep matcher, and overview
    red/blue links all read topic_index.json.
  - render_audio may write mp3 paths back into analysis.json; it mutates
    the shared corpus dicts identically, so later stages see disk truth.
  - sweep rematch + overviews precede build_index, which reads their
    coverage stats for the explore strip.

Usage:
    python build.py [--force]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import load_corpus
from lib.questions_store import load_store
from lib.crossref.crossref import rebuild_index
from lib.rerender import render_all
from lib.render import render_audio, render_cards, render_questions, render_score_review
from lib.render.build_overviews import build as build_overviews
from lib.sweep.build_set import rematch_all
from lib.sweep.matcher import TopicMatcher
from lib.build_index import build as build_index
from lib import validate
from dev import build_changelog, build_crossrefs, build_stats


def main() -> None:
    force = "--force" in sys.argv

    t0 = time.time()
    analyses, parse_errors = load_corpus()
    for path, msg in parse_errors:
        print(f"WARNING: skipping {path}: {msg}", file=sys.stderr)
    store = load_store()
    print(f"Loaded {len(analyses)} analyses + {len(store)} stored questions "
          f"in {time.time() - t0:.1f}s")

    rebuild_index(analyses=analyses)
    render_all(force=force, analyses=analyses)
    render_cards.build_all(force=force, analyses=analyses)
    render_questions.build_all(force=force, analyses=analyses)
    render_audio.build_all(force=force, analyses=analyses)
    render_score_review.main(analyses=analyses)

    build_stats.main(analyses=analyses)
    build_changelog.main()
    build_crossrefs.main(analyses=analyses)

    # One matcher serves both the sweep rematch and overview rendering.
    matcher = TopicMatcher(analyses=analyses)
    rematch_all(matcher=matcher)
    build_overviews(force=force, matcher=matcher)

    build_index(analyses=analyses)
    validate.main(analyses=analyses, parse_errors=parse_errors, store=store)
    print("Done.")


if __name__ == "__main__":
    main()
