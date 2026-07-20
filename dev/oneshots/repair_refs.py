"""repair_refs.py — retroactively apply word-boundary answer matching to
committed questions_ref.json files.

Historic fetches used the API's bare substring match, which attributed
foreign questions to topics ("Hanson" ⊂ "Chanson de Roland", "Edward I" ⊂
"Charles Edward Ives"/"Edward III"). fetch.py now queries with
exact_phrase=True; this script prunes the already-committed id lists with
the SAME predicate (mirror_query._compile_words + _matches) so refs match
what a fresh fetch would return.

Purely subtractive: ids whose mirror row no longer matches are dropped;
nothing is re-queried, so no new ids appear. Ids missing from the mirror
are kept (conservative). Default is a dry-run report; --apply writes.

Usage: python dev/oneshots/repair_refs.py [--apply] [--verbose]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.common import OUTPUT_DIR, write_json_if_changed
from qbmirror import db as mirror_db
from qbmirror.query import _compile_words, _matches


def _texts_for(row, kind: str, mentions: bool) -> list[str]:
    """The fields the original search matched against, per query type."""
    if kind == "tossup":
        return [row["question_sanitized"] if mentions else row["answer_sanitized"]]
    if mentions:
        return [row["leadin_sanitized"] or ""] + json.loads(row["parts_sanitized"] or "[]")
    return json.loads(row["answers_sanitized"] or "[]")


def repair(apply: bool, verbose: bool) -> None:
    conn = mirror_db.open_db()
    row_cache: dict[tuple, object] = {}

    def fetch_row(kind, id_):
        key = (kind, id_)
        if key not in row_cache:
            table = "tossups" if kind == "tossup" else "bonuses"
            row_cache[key] = conn.execute(
                f"SELECT * FROM {table} WHERE id=?", (id_,)).fetchone()
        return row_cache[key]

    topics_changed = total_dropped = total_kept = 0
    for ref_path in sorted(OUTPUT_DIR.glob("*/questions_ref.json")):
        slug = ref_path.parent.name
        entries = json.loads(ref_path.read_text(encoding="utf-8"))
        dropped_here = []
        for entry in entries:
            _, patterns = _compile_words(
                entry["query_string"], exact_phrase=True,
                ignore_word_order=False, case_sensitive=False, regex=False)
            mentions = bool(entry.get("mentions"))
            for kind, id_key in (("tossup", "tossups"), ("bonus", "bonuses")):
                kept = []
                for id_ in entry.get(id_key, []):
                    row = fetch_row(kind, id_)
                    if row is None or _matches(patterns, _texts_for(row, kind, mentions)):
                        kept.append(id_)
                    else:
                        answer = (row["answer_sanitized"] if kind == "tossup"
                                  else row["answers_sanitized"]) or ""
                        dropped_here.append(
                            (entry["query_string"], mentions, kind, id_, answer[:90]))
                entry[id_key] = kept
        total_kept += sum(len(e.get(k, [])) for e in entries
                          for k in ("tossups", "bonuses"))
        if dropped_here:
            topics_changed += 1
            total_dropped += len(dropped_here)
            print(f"\n{slug}: dropping {len(dropped_here)}")
            shown = dropped_here if verbose else dropped_here[:5]
            for q, mentions, kind, id_, answer in shown:
                tier = "mentions" if mentions else "answer"
                print(f"  [{tier}/{kind}] query={q!r} answer={answer!r}")
            if not verbose and len(dropped_here) > 5:
                print(f"  ... {len(dropped_here) - 5} more (--verbose to list)")
            if apply:
                write_json_if_changed(ref_path, entries)
    conn.close()

    mode = "APPLIED" if apply else "DRY-RUN (no files written; use --apply)"
    print(f"\n{mode}: {topics_changed} topics affected, "
          f"{total_dropped} ids dropped, {total_kept} kept")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    repair(args.apply, args.verbose)
