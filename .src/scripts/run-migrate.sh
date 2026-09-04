#!/bin/bash
# Safely migrate legacy Pensieve data without overwriting project-owned content.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

usage() {
  cat <<'USAGE'
Usage: run-migrate.sh [options]

Options:
  --root <path>             Target data root. Default: <project>/.pensieve
  --state-dir <path>        Runtime state dir. Default: <project>/.pensieve/.state
  --report <path>           Markdown report path
  --summary-json <path>     JSON summary path
  --backup-dir <path>       Full legacy backup destination
  --client <name>           auto | codex | claude | both | generic
  --cleanup-legacy          Delete legacy locations only after every backup verifies
  --dry-run                 Plan only; write nothing
  -h, --help                Show help
USAGE
}

ROOT=""
STATE_DIR=""
REPORT=""
SUMMARY_JSON=""
BACKUP_DIR=""
CLIENT_REQUEST="${PENSIEVE_CLIENT:-auto}"
CLEANUP_LEGACY=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) [[ $# -ge 2 ]] || { echo "Missing value for --root" >&2; exit 1; }; ROOT="$2"; shift 2 ;;
    --state-dir) [[ $# -ge 2 ]] || { echo "Missing value for --state-dir" >&2; exit 1; }; STATE_DIR="$2"; shift 2 ;;
    --report) [[ $# -ge 2 ]] || { echo "Missing value for --report" >&2; exit 1; }; REPORT="$2"; shift 2 ;;
    --summary-json) [[ $# -ge 2 ]] || { echo "Missing value for --summary-json" >&2; exit 1; }; SUMMARY_JSON="$2"; shift 2 ;;
    --backup-dir) [[ $# -ge 2 ]] || { echo "Missing value for --backup-dir" >&2; exit 1; }; BACKUP_DIR="$2"; shift 2 ;;
    --client) [[ $# -ge 2 ]] || { echo "Missing value for --client" >&2; exit 1; }; CLIENT_REQUEST="$2"; shift 2 ;;
    --cleanup-legacy) CLEANUP_LEGACY=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

CLIENT="$(pensieve_client "$CLIENT_REQUEST" "$SCRIPT_DIR")"
export PENSIEVE_CLIENT="$CLIENT"
PROJECT_ROOT="$(project_root)" || exit 1
PROJECT_ROOT="$(to_posix_path "$PROJECT_ROOT")"
validate_project_root "$PROJECT_ROOT"
SKILL_ROOT="$(skill_root_from_script "$SCRIPT_DIR")"

[[ -n "$ROOT" ]] || ROOT="$(user_data_root)"
ROOT="$(to_posix_path "$ROOT")"
[[ -n "$STATE_DIR" ]] || STATE_DIR="$ROOT/.state"
STATE_DIR="$(resolve_output_path "$STATE_DIR" "$ROOT/.state" "$PROJECT_ROOT")"
REPORT="$(resolve_output_path "$REPORT" "$STATE_DIR/pensieve-migrate-report.md" "$PROJECT_ROOT")"
SUMMARY_JSON="$(resolve_output_path "$SUMMARY_JSON" "$STATE_DIR/pensieve-migrate-summary.json" "$PROJECT_ROOT")"
TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
[[ -n "$BACKUP_DIR" ]] || BACKUP_DIR="$STATE_DIR/migrate-backups/$TIMESTAMP"
BACKUP_DIR="$(resolve_output_path "$BACKUP_DIR" "$BACKUP_DIR" "$PROJECT_ROOT")"
ACTIONS_JSON="$STATE_DIR/pensieve-migration-actions.json"

ensure_python_env
[[ -n "${PYTHON_BIN:-}" ]] || { echo "Python not found" >&2; exit 1; }

ENGINE_ARGS=(
  --root "$ROOT"
  --project-root "$PROJECT_ROOT"
  --skill-root "$SKILL_ROOT"
  --home "${HOME:-}"
  --state-dir "$STATE_DIR"
  --report "$REPORT"
  --summary "$SUMMARY_JSON"
  --actions "$ACTIONS_JSON"
  --backup-dir "$BACKUP_DIR"
  --timestamp "$TIMESTAMP"
  --client "$CLIENT"
)
[[ "$CLEANUP_LEGACY" -eq 1 ]] && ENGINE_ARGS+=(--cleanup-legacy)
[[ "$DRY_RUN" -eq 1 ]] && ENGINE_ARGS+=(--dry-run)

"$PYTHON_BIN" "$SKILL_ROOT/.src/core/migrate_engine.py" \
  "${ENGINE_ARGS[@]}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "✅ Migrate dry-run completed (zero writes)"
  exit 0
fi

MAINTAIN_SCRIPT="$SCRIPT_DIR/maintain-project-state.sh"
if [[ -x "$MAINTAIN_SCRIPT" ]]; then
  bash "$MAINTAIN_SCRIPT" --client "$CLIENT" --event migrate --note "migration completed; cleanup_legacy=$CLEANUP_LEGACY" >/dev/null || true
fi

MARKER_SCRIPT="$SCRIPT_DIR/pensieve-session-marker.sh"
if [[ -x "$MARKER_SCRIPT" ]]; then
  bash "$MARKER_SCRIPT" --client "$CLIENT" --mode record --event migrate || true
fi

echo "✅ Migrate completed"
echo "  - client: $CLIENT"
echo "  - cleanup legacy: $([[ "$CLEANUP_LEGACY" -eq 1 ]] && echo yes || echo no)"
echo "  - report: $REPORT"
echo "  - summary: $SUMMARY_JSON"
echo "  - next: run doctor manually"
