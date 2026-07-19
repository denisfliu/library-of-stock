#!/bin/bash
# maintain.sh - fleet self-healing loop, runs on the queue host (MSL) in tmux
# session `sweep`. Every 30 min it reconciles (requeues items a stopped worker
# marked done but never synced to the host); every 4 h it also runs the
# content-based text-sweep (requeues files made with old cleaning). Together these
# guarantee the end-of-run sweep happens on its own and keep the fleet correct as
# workers pause and resume.
#   tmux new-session -d -s sweep "bash ~/los_tts/maintain.sh >> sweep.log 2>&1"
PY=~/venvs/chatterbox-tts/bin/python
i=0
while true; do
  echo "[$(date +%H:%M:%S)] reconcile"; $PY ~/los_tts/ttsqueue.py reconcile
  i=$((i+1))
  if [ $((i % 8)) -eq 0 ]; then
    echo "[$(date +%H:%M:%S)] text-sweep"; $PY ~/los_tts/verify_tts.py --no-asr --requeue 2>&1 | grep -E "REQUEUE|requeued"
  fi
  sleep 1800
done
