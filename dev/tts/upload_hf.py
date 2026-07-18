"""upload_hf.py — incrementally push generated Opus audio to a HF dataset.

Reads a write token from ~/los_tts/.hf_token (chmod 600; never passed on the
command line so it stays out of shell history), derives the account, creates
(or reuses) the dataset repo <user>/library-of-stock-audio, and starts a
CommitScheduler that commits new *.opus files under out/ every few minutes.
Also rebuilds out/audio_index.json — the list of qids that have audio — each
cycle, so the reader can restrict its queue to audio-backed questions.
Resumable and idempotent: rerunning re-syncs whatever isn't uploaded yet.

Run under tmux alongside the generator:
  ~/venvs/chatterbox-tts/bin/python upload_hf.py
"""
import json
import sys
import time
from pathlib import Path

from huggingface_hub import CommitScheduler, HfApi

WORK = Path.home() / "los_tts"
OUT = WORK / "out"
TOKEN_FILE = WORK / ".hf_token"
REPO_NAME = "qb-audio"
EVERY_MIN = 10

def build_manifest():
    """Write out/audio_index.json = {tossups:[qid...], bonuses:[qid...]} from
    the *.opus files present. Cheap directory walk; the reader loads this to
    filter its queue to questions that actually have audio."""
    idx = {}
    for kind in ("tossups", "bonuses"):
        d = OUT / kind
        idx[kind] = sorted(p.stem for p in d.rglob("*.opus")) if d.exists() else []
    (OUT / "audio_index.json").write_text(json.dumps(idx, separators=(",", ":")))
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

    build_manifest()   # so the first commit already carries the index
    scheduler = CommitScheduler(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=str(OUT),
        every=EVERY_MIN,
        allow_patterns=["**/*.opus", "audio_index.json"],
        token=token,
        squash_history=False,
    )
    print(f"CommitScheduler running: committing new *.opus + manifest every {EVERY_MIN} min", flush=True)
    try:
        while True:
            time.sleep(EVERY_MIN * 60)
            n = build_manifest()   # refresh the index just before each commit window
            print(f"[{time.strftime('%H:%M:%S')}] {n:,} audio files present locally", flush=True)
    except KeyboardInterrupt:
        scheduler.stop()

if __name__ == "__main__":
    main()
