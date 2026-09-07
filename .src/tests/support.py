from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = REPO_ROOT / ".src" / "core"
SCRIPTS_ROOT = REPO_ROOT / ".src" / "scripts"
FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"
# 由共享测试支撑统一加载仓库运行模块，避免测试模块相互导入。
sys.path.insert(0, str(CORE_ROOT))

import hook_runtime  # noqa: E402
import pensieve_core  # noqa: E402


TEST_TMP_ROOT = Path(
    os.environ.get("PENSIEVE_TEST_TMPDIR", str(Path.home() / ".cache" / "pensieve-tests"))
)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    write_text(path, json.dumps(dict(value), ensure_ascii=False, indent=2) + "\n")


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_snapshot(root: Path) -> tuple:
    items = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            items.append((relative, "symlink", os.readlink(str(path))))
        elif path.is_file():
            stat = path.stat()
            items.append((relative, "file", stat.st_mode, stat.st_mtime_ns, file_digest(path)))
        else:
            items.append((relative, "dir"))
    return tuple(items)


class PensieveTestCase(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        self._temporary = tempfile.TemporaryDirectory(prefix="case-", dir=str(TEST_TMP_ROOT))
        self.case_root = Path(self._temporary.name)
        self.project = self.case_root / "项目"
        self.home = self.case_root / "home"
        self.project.mkdir()
        self.home.mkdir()

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def env(self, project: Optional[Path] = None) -> Dict[str, str]:
        value = os.environ.copy()
        for key in (
            "CLAUDE_PROJECT_DIR",
            "CLAUDE_PLUGIN_ROOT",
            "CLAUDE_CONFIG_DIR",
            "PLUGIN_ROOT",
            "CODEX_HOME",
            "PENSIEVE_CLIENT",
            "PENSIEVE_DATA_ROOT",
            "PENSIEVE_STATE_ROOT",
            "PENSIEVE_SOURCE_ROOT",
        ):
            value.pop(key, None)
        value.update(
            {
                "HOME": str(self.home),
                "PENSIEVE_PROJECT_ROOT": str(project or self.project),
                "PENSIEVE_SKILL_ROOT": str(REPO_ROOT),
                "PYTHONIOENCODING": "utf-8",
            }
        )
        return value

    def run_script(
        self,
        name: str,
        *arguments: str,
        project: Optional[Path] = None,
        check: bool = True,
        input_text: Optional[str] = None,
        extra_env: Optional[Mapping[str, str]] = None,
    ) -> subprocess.CompletedProcess:
        selected_project = project or self.project
        environment = self.env(selected_project)
        if extra_env:
            environment.update(extra_env)
        return subprocess.run(
            ["bash", str(SCRIPTS_ROOT / name), *arguments],
            cwd=str(selected_project),
            env=environment,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def init(self, client: str = "codex", project: Optional[Path] = None) -> None:
        self.run_script("init-project-data.sh", "--client", client, project=project)

    def hook(
        self,
        client: str,
        event: str,
        payload: Mapping[str, Any],
        *,
        extra_env: Optional[Mapping[str, str]] = None,
    ) -> subprocess.CompletedProcess:
        environment = self.env()
        if extra_env:
            environment.update(extra_env)
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_ROOT / "run-client-hook.py"),
                "--client",
                client,
                "--event",
                event,
            ],
            cwd=str(self.project),
            env=environment,
            input=json.dumps(dict(payload), ensure_ascii=False),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def fixture(self, name: str) -> Dict[str, Any]:
        raw = (FIXTURES_ROOT / name).read_text(encoding="utf-8")
        return json.loads(raw.replace("__PROJECT__", str(self.project)))
