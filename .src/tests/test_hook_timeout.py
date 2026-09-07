from __future__ import annotations

import importlib.util
import os
import subprocess
import time
from unittest.mock import patch

from test_pensieve import PensieveTestCase, SCRIPTS_ROOT, write_text


HOOK_SPEC = importlib.util.spec_from_file_location("pensieve_timeout_hook", SCRIPTS_ROOT / "run-client-hook.py")
hook_runner = importlib.util.module_from_spec(HOOK_SPEC)
HOOK_SPEC.loader.exec_module(hook_runner)


class HookTimeoutTests(PensieveTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.state = self.project / ".pensieve" / ".state"
        self.state.mkdir(parents=True)

    def test_timeout_stops_real_maintenance_child_before_it_can_write_later(self) -> None:
        fixture_plugin = self.case_root / "fixture-plugin"
        maintain = fixture_plugin / ".src/scripts/maintain-project-state.sh"
        write_text(
            maintain,
            "#!/bin/bash\n"
            "bash -c 'printf started > \"$PENSIEVE_STATE_ROOT/started\"; "
            "sleep 0.5; printf late > \"$PENSIEVE_STATE_ROOT/late-output\"'\n",
        )
        original_popen = subprocess.Popen
        requested_timeouts = []

        def accelerated_popen(*args, **kwargs):
            process = original_popen(*args, **kwargs)
            original_wait = process.wait

            def wait(timeout=None):
                if timeout == 25:
                    requested_timeouts.append(timeout)
                    deadline = time.monotonic() + 2
                    while not (self.state / "started").exists() and time.monotonic() < deadline:
                        time.sleep(0.01)
                    timeout = 0.05
                return original_wait(timeout=timeout)

            process.wait = wait
            return process

        with patch.object(hook_runner, "SKILL_ROOT", fixture_plugin):
            with patch.object(hook_runner.subprocess, "Popen", side_effect=accelerated_popen):
                result = hook_runner.maintain_project("codex", self.project, ("knowledge/example/content.md",), "Write")
        self.assertFalse(result)
        self.assertEqual(requested_timeouts, [25])
        self.assertTrue((self.state / "started").is_file())
        self.assertFalse((self.state / "late-output").exists())
        time.sleep(0.7)
        self.assertFalse((self.state / "late-output").exists())

    def test_successful_real_refresh_still_creates_project_derived_state(self) -> None:
        write_text(self.project / ".pensieve/knowledge/example/content.md", "# Fixture fact\n")
        with patch.dict(os.environ, self.env()):
            result = hook_runner.maintain_project("codex", self.project, ("knowledge/example/content.md",), "Write")
        self.assertTrue(result)
        self.assertTrue((self.project / ".pensieve/state.md").is_file())
        self.assertTrue((self.state / "pensieve-user-data-graph.md").is_file())
        self.assertFalse((self.home / ".claude").exists())
        self.assertFalse((self.project / ".pensieve/decisions").exists())

    def test_maintenance_nonzero_exit_returns_failure(self) -> None:
        fixture_plugin = self.case_root / "fixture-plugin"
        write_text(fixture_plugin / ".src/scripts/maintain-project-state.sh", "#!/bin/bash\nexit 7\n")
        with patch.object(hook_runner, "SKILL_ROOT", fixture_plugin):
            self.assertFalse(hook_runner.maintain_project("codex", self.project, (), "Write"))

    def test_maintenance_launch_failure_returns_failure(self) -> None:
        with patch.object(hook_runner.subprocess, "Popen", side_effect=OSError("cannot launch fixture")):
            self.assertFalse(hook_runner.maintain_project("codex", self.project, (), "Write"))
