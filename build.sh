#!/bin/bash
# Run the full build (all renderers + validate) via the single-process
# orchestrator in build.py.
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

python build.py $FORCE
