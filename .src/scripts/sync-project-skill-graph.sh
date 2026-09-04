#!/bin/bash
# Backward-compatible Claude Code PostToolUse entry point.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"
ensure_python_env
[[ -n "${PYTHON_BIN:-}" ]] || exit 0
exec "$PYTHON_BIN" "$SCRIPT_DIR/run-client-hook.py" --client claude --event post-tool-use
