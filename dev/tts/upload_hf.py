"""upload_hf.py — incrementally push generated Opus audio to a HF dataset.

Reads a write token from ~/los_tts/.hf_token (chmod 600; never passed on the
command line so it stays out of shell history), derives the account, creates
(or reuses) the dataset repo <user>/library-of-stock-audio, and starts a
CommitScheduler that commits new *.opus files (and their {qid}.json
chunk-offset sidecars) under out/ every few minutes.
Also rebuilds out/audio_index.json — the list of qids that have audio — each
cycle, so the reader can restrict its queue to audio-backed questions.
Resumable and idempotent: rerunning re-syncs whatever isn't uploaded yet.

Run under tmux alongside the generator:
  ~/venvs/chatterbox-tts/bin/python upload_hf.py
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

from huggingface_hub import CommitScheduler, HfApi

WORK = Path.home() / "los_tts"
OUT = WORK / "out"
TOKEN_FILE = WORK / ".hf_token"
REPO_NAME = "qb-audio"
EVERY_MIN = 10

def fetch_remote_manifest(repo_id):
    """Current audio_index.json as committed to the dataset, {} if absent.
    Every fleet worker's uploader rebuilds and commits the manifest, but each
    machine's out/ only holds the shards it generated — a local-only scan from
    one worker would clobber every other worker's entries. Unioning with the
    remote copy keeps the manifest monotonic: a stale/failed fetch just delays
    another worker's additions until that worker's own next cycle re-adds them."""
    url = f"https://huggingface.co/datasets/{repo_id}/resolve/main/audio_index.json"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read())
    except Exception:
        return {}

def build_manifest(repo_id=None):
    """Write out/audio_index.json = {tossups:[qid...], bonuses:[qid...]} from
    the *.opus files present, unioned with the remote manifest (fleet workers
    each hold only their own shards). The reader loads this to filter its
    queue to questions that actually have audio."""
    remote = fetch_remote_manifest(repo_id) if repo_id else {}
    idx = {}
    for kind in ("tossups", "bonuses"):
        d = OUT / kind
        local = (p.stem for p in d.rglob("*.opus")) if d.exists() else ()
        idx[kind] = sorted(set(remote.get(kind, [])) | set(local))
    # tmp + atomic replace: the CommitScheduler snapshots this folder on its
    # own timer, and a plain write_text raced it — a truncated manifest got
    # committed (July 18, 2026) and broke the reader's read-aloud mode.
    tmp = OUT / "audio_index.json.tmp"   # .tmp matches no allow_pattern
    tmp.write_text(json.dumps(idx, separators=(",", ":")))
    tmp.replace(OUT / "audio_index.json")
    return sum(len(v) for v in idx.values())

def main():
    if not TOKEN_FILE.exists():
        sys.exit(f"no token at {TOKEN_FILE} — create it first (see instructions)")
    token = TOKEN_FILE.read_text().strip()
    api = HfApi(token=token)
    who = api.whoami()
    user = who["name"]
    repo_id = f"{user}/{REPO_NAME}"
    api.create_repo(repo_id, repo_type="dataset", exist_ok=True, private=False)
    print(f"authenticated as {user}; repo {repo_id} ready", flush=True)
    print(f"https://huggingface.co/datasets/{repo_id}", flush=True)

    build_manifest(repo_id)   # so the first commit already carries the index
    scheduler = CommitScheduler(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=str(OUT),
        every=EVERY_MIN,
        # fnmatch semantics: "**/*.json" needs a "/", so the root manifest
        # must be listed explicitly.
        allow_patterns=["**/*.opus", "**/*.json", "audio_index.json"],
        token=token,
        squash_history=False,
    )
    print(f"CommitScheduler running: committing new *.opus + manifest every {EVERY_MIN} min", flush=True)
    try:
        while True:
            time.sleep(EVERY_MIN * 60)
            n = build_manifest(repo_id)   # refresh the index just before each commit window
            print(f"[{time.strftime('%H:%M:%S')}] manifest {n:,} qids (local ∪ remote)", flush=True)
    except KeyboardInterrupt:
        scheduler.stop()

if __name__ == "__main__":
    main()
