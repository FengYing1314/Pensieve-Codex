#!/bin/bash
# Read or update the provider-neutral Pensieve lifecycle marker.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

MODE="session-start"
EVENT=""
CLIENT_REQUEST="${PENSIEVE_CLIENT:-auto}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      [[ $# -ge 2 ]] || { echo "Missing value for --mode" >&2; exit 1; }
      MODE="$2"
      shift 2
      ;;
    --event)
      [[ $# -ge 2 ]] || { echo "Missing value for --event" >&2; exit 1; }
      EVENT="$2"
      shift 2
      ;;
    --client)
      [[ $# -ge 2 ]] || { echo "Missing value for --client" >&2; exit 1; }
      CLIENT_REQUEST="$2"
      shift 2
      ;;
    -h|--help)
      cat <<'USAGE'
Usage:
  pensieve-session-marker.sh --mode session-start [--client <name>]
  pensieve-session-marker.sh --mode record --event <name> [--client <name>]
USAGE
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

case "$MODE" in
  session-start|record) ;;
  *) echo "Unsupported --mode: $MODE" >&2; exit 1 ;;
esac
if [[ "$MODE" == "record" && -z "$EVENT" ]]; then
  echo "--event is required for --mode record" >&2
  exit 1
fi

CLIENT="$(pensieve_client "$CLIENT_REQUEST" "$SCRIPT_DIR")"
export PENSIEVE_CLIENT="$CLIENT"
ensure_python_env
[[ -n "${PYTHON_BIN:-}" ]] || exit 0

SKILL_ROOT="$(skill_root_from_script "$SCRIPT_DIR")"
PROJECT_ROOT="$(project_root)" || exit 0
PROJECT_ROOT="$(to_posix_path "$PROJECT_ROOT")"

if [[ "$MODE" == "session-start" && ! -d "$PROJECT_ROOT/.pensieve" ]]; then
  exit 0
fi

SKILL_VERSION="$(skill_version "$SCRIPT_DIR")"
NOW_UTC="$(runtime_now_utc)"

"$PYTHON_BIN" - "$MODE" "$EVENT" "$CLIENT" "$PROJECT_ROOT" "$SKILL_ROOT" "$SKILL_VERSION" "$NOW_UTC" <<'PY'
from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from pathlib import Path

mode, event, client = sys.argv[1:4]
project_root = Path(sys.argv[4])
skill_root = Path(sys.argv[5])
skill_version = sys.argv[6]
now_utc = sys.argv[7]

sys.path.insert(0, str(skill_root / ".src" / "core"))
import hook_runtime

data_root = project_root / ".pensieve"
marker_file = data_root / ".state" / "pensieve-session-marker.json"


@contextlib.contextmanager
def marker_lock(state_dir: Path):
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_file = state_dir / ".marker.lock"
    stream = lock_file.open("a+")
    try:
        try:
            import fcntl
        except ImportError:
            fcntl = None
        if fcntl is not None:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            yield
        else:
            lock_dir = state_dir / ".marker.lock.d"
            for _ in range(600):
                try:
                    lock_dir.mkdir()
                    break
                except FileExistsError:
                    time.sleep(0.05)
            else:
                raise TimeoutError("timed out waiting for marker lock")
            try:
                yield
            finally:
                try:
                    lock_dir.rmdir()
                except OSError:
                    pass
    finally:
        stream.close()


def normalize_event(raw: str) -> str:
    value = raw.strip().lower()
    if value in {"init", "install"}:
        return "init"
    if value in {"selfimprove", "self-improve"}:
        return "self-improve"
    if value in {"sync", "auto-sync", "sync-instructions"}:
        return "sync"
    return value


if mode == "session-start":
    semantics = hook_runtime.session_semantics(project_root, skill_version)
    if semantics is not None:
        print(json.dumps(hook_runtime.render_context_output(client, semantics), ensure_ascii=False))
    raise SystemExit(0)

with marker_lock(marker_file.parent):
    state = hook_runtime.read_json_object(marker_file)
    if state.get("schema_version") != 1:
        state = {}
    state = {
        "schema_version": 1,
        "project_root": str(project_root),
        "skill_root": str(skill_root),
        "skill_version": str(state.get("skill_version") or skill_version),
        "initialized": bool(state.get("initialized")),
        "self_check_version": str(state.get("self_check_version") or ""),
        "self_check_at": str(state.get("self_check_at") or ""),
        "last_event": str(state.get("last_event") or ""),
        "updated_at": str(state.get("updated_at") or now_utc),
    }

    if state["skill_version"] != skill_version:
        state["skill_version"] = skill_version
        state["self_check_version"] = ""
        state["self_check_at"] = ""

    normalized = normalize_event(event)
    if normalized in {"init", "migrate"}:
        state["initialized"] = True
    elif normalized == "doctor" and state["initialized"]:
        state["self_check_version"] = skill_version
        state["self_check_at"] = now_utc
    elif normalized == "upgrade":
        state["self_check_version"] = ""
        state["self_check_at"] = ""

    state["skill_version"] = skill_version
    state["last_event"] = normalized or state["last_event"]
    state["updated_at"] = now_utc
    hook_runtime.write_text_atomic_if_changed(marker_file.parent / ".gitignore", "*\n")
    hook_runtime.write_json_atomic_if_changed(marker_file, state)
PY
