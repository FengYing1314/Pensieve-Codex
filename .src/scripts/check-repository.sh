#!/bin/bash
# 从任意工作目录运行仓库自检；PYTHON_BIN 可选择需要验证的 Python 3。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
export PYTHON_BIN
export PYTHONDONTWRITEBYTECODE=1

"$PYTHON_BIN" -c 'import sys; sys.exit("Python 3.8 or newer is required" if sys.version_info < (3, 8) else 0)'

printf '%s\n' 'Checking Shell syntax'
for script in .src/scripts/*.sh; do
  bash -n "$script"
done

printf '%s\n' 'Compiling Python sources into a temporary directory'
"$PYTHON_BIN" - <<'PY'
from pathlib import Path
import py_compile
import tempfile

with tempfile.TemporaryDirectory(prefix="pensieve-compile-") as temporary:
    output = Path(temporary)
    for directory in (".src/core", ".src/scripts", ".src/tests"):
        for source in sorted(Path(directory).rglob("*.py")):
            target = output / source.with_suffix(".pyc")
            target.parent.mkdir(parents=True, exist_ok=True)
            py_compile.compile(str(source), cfile=str(target), doraise=True)
PY

printf '%s\n' 'Running behavior parity and safety tests'
"$PYTHON_BIN" -m unittest discover -s .src/tests -p 'test_*.py' -v

printf '%s\n' 'Checking JSON manifests'
for manifest in .codex-plugin/plugin.json hooks/hooks.json .src/manifest.json .src/core/schema.json; do
  "$PYTHON_BIN" -m json.tool "$manifest" >/dev/null
done

printf '%s\n' 'Checking whitespace errors'
git diff --check

printf '%s\n' 'Repository checks passed'
