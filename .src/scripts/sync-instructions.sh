#!/bin/bash
# Sync short Pensieve routing guidance into project instruction files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

START_MARKER="<!-- pensieve:instructions:start -->"
END_MARKER="<!-- pensieve:instructions:end -->"
TARGET_MODE="all"
CUSTOM_TARGETS=()
CLIENT_REQUEST="${PENSIEVE_CLIENT:-auto}"

usage() {
  cat <<'USAGE'
Usage:
  sync-instructions.sh [options]

Options:
  --target <mode>   all | auto | claude | codex | agents. Default: all
                    all    updates/creates CLAUDE.md and AGENTS.md
                    auto   updates existing CLAUDE.md/AGENTS.md, or creates both if neither exists
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

pipeline_exists() {
  [[ -f "$PIPELINES_DIR/$1.md" ]]
}

build_instruction_block() {
  local routes=()

  if pipeline_exists "run-when-committing"; then
    routes+=("- Commit requests (\`commit\`, \`git commit\`): use \`.pensieve/pipelines/run-when-committing.md\`. Check staged diff, decide whether reusable insight should be captured, then make atomic commits.")
  fi

  if pipeline_exists "run-when-refactoring"; then
    routes+=("- Refactor requests (\`refactor\`, \`large refactor\`, \`split code\`): use \`.pensieve/pipelines/run-when-refactoring.md\`. Confirm the real problem, fix upstream data authority first, split large work into 2-3 user-visible steps, delete old paths when new paths work, and avoid compatibility/fallback branches.")
  fi

  if pipeline_exists "run-when-reviewing-code"; then
    routes+=("- Review requests (\`review\`, \`code review\`, \`inspect code\`): use \`.pensieve/pipelines/run-when-reviewing-code.md\`. Start from git history and changed hot spots, verify candidate issues, and report only high-signal findings with evidence and file locations.")
  fi

  if [[ "${#routes[@]}" -eq 0 ]]; then
    echo "No supported pipeline files found in: $PIPELINES_DIR" >&2
    echo "Expected run-when-committing.md, run-when-refactoring.md, or run-when-reviewing-code.md." >&2
    return 1
  fi

  cat <<EOF
$START_MARKER
## How To Use Pensieve

Use \`.pensieve/\` as the first source of architectural intent.

- \`maxims/\` are active engineering rules.
- \`decisions/\` are active project decisions.
- \`knowledge/\` explains boundary maps and debugging paths.
- \`pipelines/\` gives executable workflows.

Use these project pipelines directly when trigger words match; do not rediscover them through skills first.

$(printf '%s\n' "${routes[@]}")
$END_MARKER
EOF
}

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
        *)
          [[ -f "$PROJECT_ROOT/CLAUDE.md" ]] && targets+=("$PROJECT_ROOT/CLAUDE.md")
          [[ -f "$PROJECT_ROOT/AGENTS.md" ]] && targets+=("$PROJECT_ROOT/AGENTS.md")
          if [[ "${#targets[@]}" -eq 0 ]]; then
            targets+=("$PROJECT_ROOT/CLAUDE.md" "$PROJECT_ROOT/AGENTS.md")
          fi
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

sync_target_file() {
  local target="$1"
  local block_file="$2"
  local out_file existed start_count end_count

  mkdir -p "$(dirname "$target")"

  existed=0
  [[ -f "$target" ]] && existed=1

  if [[ "$existed" -eq 0 || ! -s "$target" ]]; then
    cp "$block_file" "$target"
    if [[ "$existed" -eq 0 ]]; then
      echo "created"
    else
      echo "updated"
    fi
    return 0
  fi

  start_count="$(grep -Fxc "$START_MARKER" "$target" || true)"
  end_count="$(grep -Fxc "$END_MARKER" "$target" || true)"

  if [[ "$start_count" -ne "$end_count" ]]; then
    echo "Malformed Pensieve instruction block in $target" >&2
    echo "Expected matching $START_MARKER and $END_MARKER markers." >&2
    return 1
  fi
  if [[ "$start_count" -gt 1 ]]; then
    echo "Malformed Pensieve instruction block in $target" >&2
    echo "Expected at most one $START_MARKER marker." >&2
    return 1
  fi

  out_file="$(mktemp)"
  if [[ "$start_count" -gt 0 ]]; then
    awk -v start="$START_MARKER" -v end="$END_MARKER" -v block_file="$block_file" '
      BEGIN {
        while ((getline line < block_file) > 0) {
          block = block line ORS
        }
        close(block_file)
        in_block = 0
      }
      $0 == start {
        printf "%s", block
        in_block = 1
        next
      }
      in_block {
        if ($0 == end) {
          in_block = 0
        }
        next
      }
      {
        print
      }
    ' "$target" > "$out_file"
  else
    cp "$target" "$out_file"
    printf '\n' >> "$out_file"
    cat "$block_file" >> "$out_file"
  fi

  mv "$out_file" "$target"
  echo "updated"
}

BLOCK_FILE="$(mktemp)"
build_instruction_block > "$BLOCK_FILE"

TARGETS=()
while IFS= read -r target; do
  [[ -n "$target" ]] && TARGETS+=("$target")
done < <(collect_targets)
if [[ "${#TARGETS[@]}" -eq 0 ]]; then
  echo "No instruction targets resolved." >&2
  rm -f "$BLOCK_FILE"
  exit 1
fi

echo "✅ Pensieve instruction sync completed"
echo "  - pipelines: $PIPELINES_DIR"
echo "  - targets:"

for target in "${TARGETS[@]}"; do
  status="$(sync_target_file "$target" "$BLOCK_FILE")"
  rel="${target#$PROJECT_ROOT/}"
  echo "    - $rel: $status"
done

rm -f "$BLOCK_FILE"

MARKER_SCRIPT="$SCRIPT_DIR/pensieve-session-marker.sh"
if [[ -f "$MARKER_SCRIPT" ]]; then
  bash "$MARKER_SCRIPT" --client "$CLIENT" --mode record --event sync-instructions || true
fi
