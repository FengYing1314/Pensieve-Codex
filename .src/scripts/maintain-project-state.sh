#!/bin/bash
# Maintain generated Pensieve project state.md and client-specific guidance.
#
# Usage:
#   maintain-project-state.sh --event <install|upgrade|migrate|doctor|self-improve|sync> [--note "..."]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

EVENT=""
NOTE=""
CLIENT_REQUEST="${PENSIEVE_CLIENT:-auto}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --event)
      [[ $# -ge 2 ]] || { echo "Missing value for --event" >&2; exit 1; }
      EVENT="$2"
      shift 2
      ;;
    --note)
      [[ $# -ge 2 ]] || { echo "Missing value for --note" >&2; exit 1; }
      NOTE="$2"
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
  maintain-project-state.sh --event <install|upgrade|migrate|doctor|self-improve|sync> [--note "..."] [--client <name>]

Options:
  --event <name>   Lifecycle event to record
  --note <text>    Optional one-line note
  --client <name>  auto | codex | claude | both | generic
  -h, --help       Show help
USAGE
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$EVENT" ]]; then
  echo "--event is required" >&2
  exit 1
fi

case "$EVENT" in
  install|init|upgrade|migrate|doctor|self-improve|selfimprove|sync|auto-sync)
    ;;
  *)
    echo "Unsupported --event: $EVENT" >&2
    exit 1
    ;;
esac

CLIENT="$(pensieve_client "$CLIENT_REQUEST" "$SCRIPT_DIR")"
export PENSIEVE_CLIENT="$CLIENT"

PROJECT_ROOT="$(project_root)" || exit 1
PROJECT_ROOT="$(to_posix_path "$PROJECT_ROOT")"
validate_project_root "$PROJECT_ROOT"
USER_DATA_ROOT="$(user_data_root)"
STATE_ROOT="$(ensure_state_dir "$(state_root)")"
STATE_FILE="$(project_state_file)"
GRAPH_FILE="$(project_graph_file)"
SKILL_ROOT="$(skill_root_from_script "$SCRIPT_DIR")"
GRAPH_SCRIPT="$SKILL_ROOT/.src/scripts/generate-user-data-graph.sh"
AUTO_MEMORY_SCRIPT="$SKILL_ROOT/.src/scripts/maintain-auto-memory.sh"

LOCK_DIR="$STATE_ROOT/.maintain.lock.d"
LOCK_KIND=""
release_maintenance_lock() {
  if [[ "$LOCK_KIND" == "mkdir" ]]; then
    rmdir "$LOCK_DIR" 2>/dev/null || true
  fi
}
trap release_maintenance_lock EXIT

if command -v flock >/dev/null 2>&1; then
  exec 9>"$STATE_ROOT/.maintain.lock"
  flock -w 30 9 || { echo "Timed out waiting for Pensieve maintenance lock" >&2; exit 1; }
  LOCK_KIND="flock"
else
  for _lock_attempt in $(seq 1 600); do
    if mkdir "$LOCK_DIR" 2>/dev/null; then
      LOCK_KIND="mkdir"
      break
    fi
    sleep 0.05
  done
  [[ "$LOCK_KIND" == "mkdir" ]] || { echo "Timed out waiting for Pensieve maintenance lock" >&2; exit 1; }
fi

mkdir -p "$USER_DATA_ROOT"/{maxims,decisions,knowledge,pipelines}
mkdir -p "$USER_DATA_ROOT"/short-term/{maxims,decisions,knowledge,pipelines}

if [[ -x "$GRAPH_SCRIPT" ]]; then
  bash "$GRAPH_SCRIPT" --root "$USER_DATA_ROOT" --output "$GRAPH_FILE" >/dev/null
else
  printf '%s\n' "_(graph not generated yet)_" > "$GRAPH_FILE"
fi

ensure_python_env
[[ -n "${PYTHON_BIN:-}" ]] || { echo "Python not found" >&2; exit 1; }
TODAY_UTC="$(date -u +"%Y-%m-%d")"

"$PYTHON_BIN" - "$STATE_FILE" "$GRAPH_FILE" "$EVENT" "$TODAY_UTC" "$PROJECT_ROOT" "$USER_DATA_ROOT" "$STATE_ROOT" "$NOTE" "$SKILL_ROOT" <<'PY'
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

skill_root = Path(sys.argv[9])
sys.path.insert(0, str(skill_root / ".src" / "core"))
from hook_runtime import write_text_atomic_if_changed

state_file = Path(sys.argv[1])
graph_file = Path(sys.argv[2])
event = sys.argv[3].strip()
today = sys.argv[4].strip()
project_root = sys.argv[5].strip()
user_data_root = sys.argv[6].strip()
state_root = sys.argv[7].strip()
note = (sys.argv[8] or "").strip().replace("\n", " ")


def event_display_name(raw: str) -> str:
    r = raw.lower()
    if r in {"install", "init"}:
        return "install/init"
    if r == "upgrade":
        return "upgrade"
    if r == "migrate":
        return "migrate"
    if r == "doctor":
        return "doctor"
    if r in {"sync", "auto-sync"}:
        return "auto-sync"
    return "self-improve"


def load_graph_ref() -> str:
    if not graph_file.exists():
        return "_(graph not generated yet)_"
    return f"See `.pensieve/.state/{graph_file.name}` (loaded on demand)"


def replace_section(lines: list[str], header: str, new_body: list[str]) -> list[str]:
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if start is None and line.rstrip() == header:
            start = i
        elif start is not None and i > start and line.startswith("## "):
            end = i
            break
    if start is None:
        return lines + ["", header] + new_body
    return lines[: start + 1] + new_body + lines[end:]


def scan_short_term() -> tuple[int, int]:
    """Return (total, due) counts for short-term items."""
    st_dir = Path(user_data_root) / "short-term"
    if not st_dir.is_dir():
        return 0, 0
    total = 0
    due = 0
    ttl_days = 7
    date_re = re.compile(r"^created:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
    try:
        today_date = dt.date.fromisoformat(today)
    except ValueError:
        today_date = dt.date.today()
    for f in sorted(st_dir.rglob("*.md")):
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")[:1024]
        fm_end = text.find("\n---", 4)
        if fm_end < 0:
            continue
        fm = text[:fm_end]
        tags_idx = fm.find("tags:")
        if tags_idx >= 0 and "seed" in fm[tags_idx:].split("\n")[0].lower():
            continue
        m = date_re.search(fm)
        if not m:
            continue
        try:
            created = dt.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        total += 1
        if (today_date - created).days >= ttl_days:
            due += 1
    return total, due


event_name = event_display_name(event)
graph_markdown = load_graph_ref()
last_note = note if note else "(none)"
st_total, st_due = scan_short_term()

if state_file.exists():
    text = state_file.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    lines = replace_section(
        lines,
        "## Lifecycle State",
        [
            f"- Last Event: {event_name}",
            f"- Last Note: {last_note}",
            "",
        ],
    )

    lines = replace_section(
        lines,
        "## Project Paths",
        [
            f"- Project Root: `{project_root}`",
            f"- User Data: `.pensieve/`",
            f"- Runtime State: `.pensieve/.state/`",
            "",
        ],
    )

    lines = replace_section(
        lines,
        "## Short-Term",
        [
            f"- Total: {st_total}",
            f"- Due for refine: {st_due} (created 7+ days ago)",
            "",
        ],
    )

    lines = replace_section(
        lines,
        "## Graph",
        [
            "",
            graph_markdown,
            "",
        ],
    )

    write_text_atomic_if_changed(state_file, "\n".join(lines).rstrip() + "\n")
else:
    content = f"""# Pensieve Project State

## Lifecycle State
- Last Event: {event_name}
- Last Note: {last_note}

## Project Paths
- Project Root: `{project_root}`
- User Data: `.pensieve/`
- Runtime State: `.pensieve/.state/`

## Short-Term
- Total: {st_total}
- Due for refine: {st_due} (created 7+ days ago)

## Graph

{graph_markdown}
"""
    write_text_atomic_if_changed(state_file, content.rstrip() + "\n")
PY

echo "✅ Pensieve project state updated"
echo "  - state: $STATE_FILE"
echo "  - graph: $GRAPH_FILE"

if client_includes "$CLIENT" claude && [[ -x "$AUTO_MEMORY_SCRIPT" ]]; then
  if ! bash "$AUTO_MEMORY_SCRIPT" --client "$CLIENT" --event "$EVENT"; then
    echo "⚠️  Auto memory update skipped: failed to run maintain-auto-memory.sh" >&2
  fi
fi
