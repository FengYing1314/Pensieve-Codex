#!/bin/bash
# Install Pensieve hooks into ~/.claude/settings.json.
# Idempotent — safe to run repeatedly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

SKILL_ROOT="$(skill_root_from_script "$SCRIPT_DIR")"
ensure_home || { echo "Cannot determine home directory" >&2; exit 1; }
CLAUDE_SETTINGS_ROOT="$(claude_config_root)"
SETTINGS_FILE="$CLAUDE_SETTINGS_ROOT/settings.json"

ensure_python_env
[[ -n "${PYTHON_BIN:-}" ]] || { echo "Python not found" >&2; exit 1; }

mkdir -p "$(dirname "$SETTINGS_FILE")"

"$PYTHON_BIN" - "$SETTINGS_FILE" "$SKILL_ROOT" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

settings_file = Path(sys.argv[1])
skill_root = sys.argv[2]
sys.path.insert(0, str(Path(skill_root) / ".src" / "core"))
from hook_runtime import write_text_atomic_if_changed

run_hook = f"{skill_root}/.src/scripts/run-hook.sh"

# Hook definitions for Pensieve
pensieve_hooks = {
    "SessionStart": [
        {
            "matcher": "startup|resume|clear|compact",
            "hooks": [
                {
                    "type": "command",
                    "command": f'bash "{run_hook}" run-client-hook.py --client claude --event session-start',
                    "timeout": 10,
                }
            ]
        }
    ],
    "SubagentStart": [
        {
            "matcher": "Explore|Plan",
            "hooks": [
                {
                    "type": "command",
                    "command": f'bash "{run_hook}" run-client-hook.py --client claude --event subagent-start',
                    "timeout": 10,
                }
            ],
        }
    ],
    "PostToolUse": [
        {
            "matcher": "Write|Edit|MultiEdit",
            "hooks": [
                {
                    "type": "command",
                    "command": f'bash "{run_hook}" run-client-hook.py --client claude --event post-tool-use',
                    "timeout": 30,
                    "async": True,
                }
            ],
        }
    ],
}

# Load existing settings
settings: dict = {}
if settings_file.exists():
    try:
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: {settings_file} contains invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error reading {settings_file}: {e}", file=sys.stderr)
        sys.exit(1)

if not isinstance(settings, dict):
    print(f"Error: {settings_file} must contain a JSON object", file=sys.stderr)
    sys.exit(1)

hooks = settings.get("hooks")
if hooks is None:
    hooks = {}
    settings["hooks"] = hooks
elif not isinstance(hooks, dict):
    print(f"Error: {settings_file} hooks must be a JSON object", file=sys.stderr)
    sys.exit(1)


known_hook_scripts = (
    "run-client-hook.py",
    "pensieve-session-marker.sh",
    "explore-prehook.sh",
    "sync-project-skill-graph.sh",
)


def is_pensieve_hook(entry: dict) -> bool:
    """Check if a hook entry belongs to Pensieve."""
    if not isinstance(entry, dict):
        return False
    for h in entry.get("hooks", []):
        if not isinstance(h, dict):
            continue
        cmd = h.get("command", "")
        if "pensieve" in cmd.lower() and any(script in cmd for script in known_hook_scripts):
            return True
    return False


# Clean up legacy v1 marketplace entry (claude-plugin branch, now obsolete)
marketplaces = settings.get("extraKnownMarketplaces")
if isinstance(marketplaces, dict):
    legacy_keys = [
        k for k, v in marketplaces.items()
        if isinstance(v, dict)
        and "kingkongshot/Pensieve" in json.dumps(v)
    ]
    for k in legacy_keys:
        del marketplaces[k]
    if legacy_keys:
        if not marketplaces:
            del settings["extraKnownMarketplaces"]
        changed_marketplace = True
    else:
        changed_marketplace = False
else:
    changed_marketplace = False

changed = changed_marketplace
managed_events = set(pensieve_hooks) | {"PreToolUse"}
for event_name in sorted(managed_events):
    new_entries = pensieve_hooks.get(event_name, [])
    existing = hooks.get(event_name, [])
    if not isinstance(existing, list):
        print(f"Error: {settings_file} hooks.{event_name} must be a JSON array", file=sys.stderr)
        sys.exit(1)

    # Remove any existing Pensieve hooks
    filtered = [e for e in existing if not is_pensieve_hook(e)]

    # Append new Pensieve hooks
    updated = filtered + new_entries

    if updated != existing:
        changed = True
    if updated:
        hooks[event_name] = updated
    else:
        hooks.pop(event_name, None)

if changed:
    write_text_atomic_if_changed(
        settings_file,
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
    )
    print(f"✅ Hooks installed to {settings_file}")
    if changed_marketplace:
        print(f"  - Cleaned up legacy v1 marketplace entries")
else:
    print(f"✅ Hooks already up to date in {settings_file}")
PY
