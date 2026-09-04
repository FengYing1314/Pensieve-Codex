#!/bin/bash
# Safely update a clean Git checkout with fast-forward-only semantics.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

usage() {
  cat <<'USAGE'
Usage: run-upgrade.sh [options]

Options:
  --state-dir <path>        Runtime state dir. Default: <project>/.pensieve/.state
  --report <path>           Upgrade markdown report path
  --summary-json <path>     Upgrade JSON summary path
  --client <name>           auto | codex | claude | both | generic
  --source-root <path>      Clean source checkout for an installed plugin snapshot
  --skip-version-check      Do not pull; only record current version
  --dry-run                 Validate and show the pull; write nothing
  -h, --help                Show help
USAGE
}

STATE_DIR=""
REPORT=""
SUMMARY_JSON=""
SOURCE_ROOT="${PENSIEVE_SOURCE_ROOT:-}"
CLIENT_REQUEST="${PENSIEVE_CLIENT:-auto}"
SKIP_VERSION_CHECK=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --state-dir) [[ $# -ge 2 ]] || { echo "Missing value for --state-dir" >&2; exit 1; }; STATE_DIR="$2"; shift 2 ;;
    --report) [[ $# -ge 2 ]] || { echo "Missing value for --report" >&2; exit 1; }; REPORT="$2"; shift 2 ;;
    --summary-json) [[ $# -ge 2 ]] || { echo "Missing value for --summary-json" >&2; exit 1; }; SUMMARY_JSON="$2"; shift 2 ;;
    --client) [[ $# -ge 2 ]] || { echo "Missing value for --client" >&2; exit 1; }; CLIENT_REQUEST="$2"; shift 2 ;;
    --source-root) [[ $# -ge 2 ]] || { echo "Missing value for --source-root" >&2; exit 1; }; SOURCE_ROOT="$2"; shift 2 ;;
    --skip-version-check) SKIP_VERSION_CHECK=1; shift ;;
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
INSTALLED_ROOT="$(skill_root_from_script "$SCRIPT_DIR")"

IS_CODEX_SNAPSHOT=0
if client_includes "$CLIENT" codex; then
  case "${INSTALLED_ROOT//\\//}" in
    */.codex/plugins/cache/*) IS_CODEX_SNAPSHOT=1 ;;
  esac
  if [[ -n "${PLUGIN_ROOT:-}" && "$(to_posix_path "$PLUGIN_ROOT")" == "$INSTALLED_ROOT" ]]; then
    IS_CODEX_SNAPSHOT=1
  fi
fi

if [[ "$IS_CODEX_SNAPSHOT" -eq 1 && -z "$SOURCE_ROOT" ]]; then
  echo "Installed Codex plugin snapshots are not updated in place." >&2
  echo "Pass --source-root <clean-git-checkout>, then reinstall the plugin from its marketplace." >&2
  exit 1
fi

if [[ -n "$SOURCE_ROOT" ]]; then
  UPDATE_ROOT="$(to_posix_path "$SOURCE_ROOT")"
else
  UPDATE_ROOT="$INSTALLED_ROOT"
fi

if [[ "$IS_CODEX_SNAPSHOT" -eq 1 && "$UPDATE_ROOT" == "$INSTALLED_ROOT" ]]; then
  echo "Refusing to treat the installed Codex snapshot as its update source." >&2
  exit 1
fi

if ! git -C "$UPDATE_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [[ "$CLIENT" == "codex" ]]; then
    echo "Installed Codex plugin snapshots are not updated in place." >&2
    echo "Pass --source-root <clean-git-checkout>, update it, then reinstall the plugin from its marketplace." >&2
  else
    echo "Pensieve upgrade requires a Git checkout: $UPDATE_ROOT" >&2
  fi
  exit 1
fi

UPDATE_ROOT_REAL="$(cd "$UPDATE_ROOT" && pwd -P)"
GIT_TOP_LEVEL="$(git -C "$UPDATE_ROOT" rev-parse --show-toplevel)"
GIT_TOP_LEVEL="$(to_posix_path "$GIT_TOP_LEVEL")"
if [[ "$UPDATE_ROOT_REAL" != "$GIT_TOP_LEVEL" ]]; then
  echo "Refusing to upgrade from a subdirectory of another Git repository: $UPDATE_ROOT" >&2
  echo "Pass the Pensieve checkout root itself." >&2
  exit 1
fi

MANIFEST_FILE="$UPDATE_ROOT/.src/manifest.json"
if [[ "$(json_get_value "$MANIFEST_FILE" "name" "")" != "pensieve" ]]; then
  echo "Refusing to upgrade an unrecognized checkout: $UPDATE_ROOT" >&2
  echo "Expected .src/manifest.json with name=pensieve." >&2
  exit 1
fi
for required_path in SKILL.md .src/core/schema.json .src/scripts/run-upgrade.sh; do
  if [[ ! -f "$UPDATE_ROOT/$required_path" ]]; then
    echo "Refusing to upgrade an incomplete Pensieve checkout: missing $required_path" >&2
    exit 1
  fi
done

if [[ -n "$(git -C "$UPDATE_ROOT" status --porcelain --untracked-files=normal)" ]]; then
  echo "Refusing to upgrade a dirty Pensieve checkout: $UPDATE_ROOT" >&2
  echo "Commit or otherwise resolve local changes first; no files were changed." >&2
  exit 1
fi

PRE_VERSION="$(PENSIEVE_SKILL_ROOT="$UPDATE_ROOT" skill_version "$UPDATE_ROOT")"
POST_VERSION="$PRE_VERSION"
UPDATE_STRATEGY="skipped"
PULL_OUTPUT=""

if [[ "$SKIP_VERSION_CHECK" -eq 0 ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    UPDATE_STRATEGY="git-pull-ff-dry-run"
    echo "[dry-run] git -C $UPDATE_ROOT pull --ff-only"
  else
    if ! PULL_OUTPUT="$(git -C "$UPDATE_ROOT" pull --ff-only 2>&1)"; then
      echo "$PULL_OUTPUT" >&2
      echo "Fast-forward upgrade failed; Pensieve did not reset or rewrite the checkout." >&2
      exit 1
    fi
    UPDATE_STRATEGY="git-pull-ff"
    [[ -z "$PULL_OUTPUT" ]] || printf '%s\n' "$PULL_OUTPUT"
  fi
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "✅ Upgrade dry-run completed (zero report/state writes)"
  exit 0
fi

POST_VERSION="$(PENSIEVE_SKILL_ROOT="$UPDATE_ROOT" skill_version "$UPDATE_ROOT")"
[[ -n "$STATE_DIR" ]] || STATE_DIR="$(state_root)"
STATE_DIR="$(resolve_output_path "$STATE_DIR" "$PROJECT_ROOT/.pensieve/.state" "$PROJECT_ROOT")"
REPORT="$(resolve_output_path "$REPORT" "$STATE_DIR/pensieve-upgrade-report.md" "$PROJECT_ROOT")"
SUMMARY_JSON="$(resolve_output_path "$SUMMARY_JSON" "$STATE_DIR/pensieve-upgrade-summary.json" "$PROJECT_ROOT")"

ensure_python_env
[[ -n "${PYTHON_BIN:-}" ]] || { echo "Python not found" >&2; exit 1; }
"$PYTHON_BIN" - "$REPORT" "$SUMMARY_JSON" "$PRE_VERSION" "$POST_VERSION" "$UPDATE_STRATEGY" "$UPDATE_ROOT" "$INSTALLED_ROOT" "$CLIENT" "$IS_CODEX_SNAPSHOT" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

report_file = Path(sys.argv[1])
summary_file = Path(sys.argv[2])
pre_version, post_version, strategy = sys.argv[3:6]
update_root, installed_root, client = sys.argv[6:9]
is_codex_snapshot = sys.argv[9] == "1"
sys.path.insert(0, str(Path(installed_root) / ".src" / "core"))
from hook_runtime import write_json_atomic_if_changed, write_text_atomic_if_changed

reinstall_required = is_codex_snapshot
summary = {
    "status": "DONE",
    "client": client,
    "pre_version": pre_version,
    "post_version": post_version,
    "version_changed": pre_version != post_version,
    "update_strategy": strategy,
    "update_root": update_root,
    "installed_root": installed_root,
    "codex_reinstall_required": reinstall_required,
    "next_action": "reinstall Codex plugin, then run doctor" if reinstall_required else "run doctor",
}
lines = [
    "# Pensieve Upgrade Report",
    "",
    f"- Status: {summary['status']}",
    f"- Client: {client}",
    f"- Pre-upgrade version: {pre_version}",
    f"- Post-upgrade version: {post_version}",
    f"- Update strategy: {strategy}",
    f"- Source checkout: `{update_root}`",
    f"- Codex reinstall required: {'yes' if reinstall_required else 'no'}",
    "",
    "Only `git pull --ff-only` is permitted. A failed non-fast-forward update stops without reset or history rewriting.",
    "",
    f"Next: {summary['next_action']}.",
]
write_json_atomic_if_changed(summary_file, summary)
write_text_atomic_if_changed(report_file, "\n".join(lines).rstrip() + "\n")
PY

MAINTAIN_SCRIPT="$SCRIPT_DIR/maintain-project-state.sh"
if [[ -x "$MAINTAIN_SCRIPT" ]]; then
  bash "$MAINTAIN_SCRIPT" --client "$CLIENT" --event upgrade --note "upgrade completed: $PRE_VERSION -> $POST_VERSION ($UPDATE_STRATEGY)" >/dev/null || true
fi
MARKER_SCRIPT="$SCRIPT_DIR/pensieve-session-marker.sh"
if [[ -x "$MARKER_SCRIPT" ]]; then
  bash "$MARKER_SCRIPT" --client "$CLIENT" --mode record --event upgrade || true
fi

echo "✅ Upgrade completed"
echo "  - client: $CLIENT"
echo "  - pre_version: $PRE_VERSION"
echo "  - post_version: $POST_VERSION"
echo "  - strategy: $UPDATE_STRATEGY"
if [[ "$IS_CODEX_SNAPSHOT" -eq 1 ]]; then
  echo "  - next: reinstall the Codex plugin from its configured marketplace"
else
  echo "  - next: run doctor"
fi
