"""push_out.py — mirror a worker's freshly-generated out/ to the queue host.

A non-host worker must NOT run its own HF uploader: upload_hf builds the
audio_index.json manifest from the *local* out/, so two uploaders would clobber
each other's manifest (and conflict on the dataset's git history). Instead each
extra worker ships its files to the host's out/, and the host's single uploader
pushes them to HF and owns the union manifest.

Every INTERVAL this scans out/ for *.opus/*.json not yet sent and streams them to
HOST:~/los_tts/out/ via `tar | ssh host tar x` (one round-trip per batch, creates
the shard subdirs, no rsync needed). Sent paths are recorded in out/.pushed so a
restart only sends new files. Idempotent.

Usage (alongside gen_tts on the worker):
  python push_out.py --host msl
"""
import argparse
import subprocess
import time
from pathlib import Path

from ttscorpus import OUT

PUSHED = OUT / ".pushed"


def load_pushed():
    return set(PUSHED.read_text().split()) if PUSHED.exists() else set()


def push(host, remote_out, files):
    """tar the given out/-relative paths and extract them on the host."""
    rel = [str(f.relative_to(OUT)).replace("\\", "/") for f in files]
    tar = subprocess.Popen(["tar", "cf", "-", "-C", str(OUT), *rel], stdout=subprocess.PIPE)
    ssh = subprocess.run(["ssh", host, f"tar xf - -C {remote_out}"],
                         stdin=tar.stdout, capture_output=True, text=True)
    tar.stdout.close()
    tar.wait()
    if ssh.returncode != 0 or tar.returncode != 0:
        raise RuntimeError(f"push failed: {ssh.stderr[:200]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True, help="ssh host of the queue/uploader (e.g. msl)")
    ap.add_argument("--remote-out", default="~/los_tts/out", help="out/ path on the host")
    ap.add_argument("--interval", type=int, default=180, help="seconds between syncs")
    ap.add_argument("--batch", type=int, default=400, help="max files per tar round-trip")
    args = ap.parse_args()

    pushed = load_pushed()
    print(f"push_out -> {args.host}:{args.remote_out}  every {args.interval}s "
          f"({len(pushed):,} already sent)", flush=True)
    while True:
        # .opus implies its .json sidecar (written first), so enumerate by .opus
        # and carry the sidecar along; only send fully-landed pairs.
        new = []
        for opus in OUT.rglob("*.opus"):
            key = str(opus.relative_to(OUT)).replace("\\", "/")
            if key in pushed:
                continue
            sc = opus.with_suffix(".json")
            new.append(opus)
            if sc.exists():
                new.append(sc)
        if new:
            for i in range(0, len(new), args.batch):
                chunk = new[i:i + args.batch]
                try:
                    push(args.host, args.remote_out, chunk)
                    for f in chunk:
                        if f.suffix == ".opus":
                            pushed.add(str(f.relative_to(OUT)).replace("\\", "/"))
                except Exception as e:
                    print(f"  push error (will retry next cycle): {e}", flush=True)
                    break
            PUSHED.write_text("\n".join(sorted(pushed)))
            print(f"[{time.strftime('%H:%M:%S')}] pushed, {len(pushed):,} total sent", flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
