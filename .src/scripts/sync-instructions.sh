#!/bin/bash
# Sync short Pensieve routing guidance into project instruction files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

START_MARKER="<!-- pensieve:instructions:start -->"
END_MARKER="<!-- pensieve:instructions:end -->"
TARGET_MODE="auto"
CUSTOM_TARGETS=()
CLIENT_REQUEST="${PENSIEVE_CLIENT:-auto}"

usage() {
  cat <<'USAGE'
Usage:
  sync-instructions.sh [options]

Options:
  --target <mode>   all | auto | claude | codex | agents. Default: auto
                    all    updates/creates CLAUDE.md and AGENTS.md
                    auto   selects only the active client's file; generic mode updates existing files only
                    claude updates/creates CLAUDE.md
                    codex  updates/creates AGENTS.md
                    agents compatibility alias for codex
  --client <name>   auto | codex | claude | both | generic
  --file <path>     Update a specific instruction file. May be repeated.
  -h, --help        Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      [[ $# -ge 2 ]] || { echo "Missing value for --target" >&2; exit 1; }
      TARGET_MODE="$2"
      shift 2
      ;;
    --file)
      [[ $# -ge 2 ]] || { echo "Missing value for --file" >&2; exit 1; }
      CUSTOM_TARGETS+=("$2")
      shift 2
      ;;
    --client)
      [[ $# -ge 2 ]] || { echo "Missing value for --client" >&2; exit 1; }
      CLIENT_REQUEST="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

CLIENT="$(pensieve_client "$CLIENT_REQUEST" "$SCRIPT_DIR")"
export PENSIEVE_CLIENT="$CLIENT"

PROJECT_ROOT="$(project_root)" || exit 1
PROJECT_ROOT="$(to_posix_path "$PROJECT_ROOT")"
validate_project_root "$PROJECT_ROOT"

DATA_ROOT="$(user_data_root)"
DATA_ROOT="$(to_posix_path "$DATA_ROOT")"
PIPELINES_DIR="$DATA_ROOT/pipelines"

if [[ ! -d "$PIPELINES_DIR" ]]; then
  echo "Missing Pensieve pipelines directory: $PIPELINES_DIR" >&2
  echo "Run init before syncing instruction files." >&2
  exit 1
fi

resolve_target_path() {
  local raw="$1"
  raw="$(to_posix_path "$raw")"
  if [[ "$raw" == /* ]]; then
    echo "$raw"
  else
    echo "$PROJECT_ROOT/$raw"
  fi
}

collect_targets() {
  local targets=()

  if [[ "${#CUSTOM_TARGETS[@]}" -gt 0 ]]; then
    local custom
    for custom in "${CUSTOM_TARGETS[@]}"; do
      targets+=("$(resolve_target_path "$custom")")
    done
    printf '%s\n' "${targets[@]}"
    return 0
  fi

  case "$TARGET_MODE" in
    all)
      targets+=("$PROJECT_ROOT/CLAUDE.md" "$PROJECT_ROOT/AGENTS.md")
      ;;
    auto)
      case "$CLIENT" in
        codex)
          targets+=("$PROJECT_ROOT/AGENTS.md")
          ;;
        claude)
          targets+=("$PROJECT_ROOT/CLAUDE.md")
          ;;
        both)
          targets+=("$PROJECT_ROOT/CLAUDE.md" "$PROJECT_ROOT/AGENTS.md")
          ;;
        *)
          [[ -f "$PROJECT_ROOT/CLAUDE.md" ]] && targets+=("$PROJECT_ROOT/CLAUDE.md")
          [[ -f "$PROJECT_ROOT/AGENTS.md" ]] && targets+=("$PROJECT_ROOT/AGENTS.md")
          ;;
      esac
      ;;
    claude)
      targets+=("$PROJECT_ROOT/CLAUDE.md")
      ;;
    codex|agents|agent)
      targets+=("$PROJECT_ROOT/AGENTS.md")
      ;;
    *)
      echo "Unsupported --target: $TARGET_MODE" >&2
      usage
      exit 1
      ;;
  esac

  printf '%s\n' "${targets[@]}"
}

ensure_python_env
[[ -n "${PYTHON_BIN:-}" ]] || { echo "Python not found" >&2; exit 1; }

TARGETS=()
TARGET_TEXT="$(collect_targets)"
while IFS= read -r target; do
  [[ -n "$target" ]] && TARGETS+=("$target")
done <<< "$TARGET_TEXT"
if [[ "${#TARGETS[@]}" -eq 0 ]]; then
  echo "No instruction targets resolved. Use --client codex|claude|both or an explicit --target/--file." >&2
  exit 1
fi

"$PYTHON_BIN" - "$SCRIPT_DIR" "$DATA_ROOT" "$CLIENT" "${TARGETS[@]}" <<'SYNC_PY'
from pathlib import Path
import os
import signal
import subprocess
import sys

script_dir = Path(sys.argv[1])
data_root = Path(sys.argv[2])
client = sys.argv[3]
sys.path.insert(0, str(script_dir.parent / "core"))
from pensieve_core import sync_instruction_targets, InstructionSyncError


try:
    results = sync_instruction_targets(data_root, [Path(raw) for raw in sys.argv[4:]])
except InstructionSyncError as exc:
    sys.exit(str(exc))
written = any(status != "unchanged" for _, status in results)


print("Pensieve instruction sync completed")
for target, status in results:
    print(f"  - {target.name}: {status}")
marker = script_dir / "pensieve-session-marker.sh"
if written and marker.is_file():
    try:
        with subprocess.Popen(
            ["bash", str(marker), "--client", client, "--mode", "record", "--event", "sync-instructions"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=(os.name == "posix"),
        ) as process:
            try:
                returncode = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # 结束整个维护进程组，避免等待锁的子进程稍后继续写入。
                if os.name == "posix":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    process.kill()
                process.wait()
                print("Instruction files were synced, but the session marker refresh timed out after 10 seconds.", file=sys.stderr)
            else:
                if returncode:
                    print("Instruction files were synced, but the session marker could not be refreshed.", file=sys.stderr)
    except OSError:
        print("Instruction files were synced, but the session marker could not be refreshed.", file=sys.stderr)
SYNC_PY
