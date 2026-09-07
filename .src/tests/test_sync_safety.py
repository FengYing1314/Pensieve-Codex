from __future__ import annotations

import contextlib
import io
import os
import signal
import subprocess
import sys
from unittest.mock import MagicMock, patch

from support import PensieveTestCase, SCRIPTS_ROOT, pensieve_core, tree_snapshot, write_text


class SyncSafetyTests(PensieveTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.init("codex")
        self.data_root = self.project / ".pensieve"

    def deny_directory_write(self, directory):
        original_access = os.access

        def check_access(path, mode):
            if path == directory and mode & os.W_OK:
                return False
            return original_access(path, mode)

        return patch.object(pensieve_core.os, "access", side_effect=check_access)

    def test_unchanged_read_only_target_does_not_block_another_update(self) -> None:
        read_only = self.project / "shared" / "CLAUDE.md"
        block = pensieve_core.instruction_block(pensieve_core.instruction_routes(self.data_root))
        write_text(read_only, block)
        read_only.parent.chmod(0o555)
        read_only.chmod(0o444)
        other = self.project / "AGENTS.md"
        write_text(other, "User instructions\n")
        before = tree_snapshot(read_only.parent)
        try:
            with self.deny_directory_write(read_only.parent):
                results = pensieve_core.sync_instruction_targets(self.data_root, [read_only, other])
                repeated = pensieve_core.sync_instruction_targets(self.data_root, [read_only])
            self.assertEqual(results, [(read_only, "unchanged"), (other, "updated")])
            self.assertEqual(repeated, [(read_only, "unchanged")])
            self.assertEqual(tree_snapshot(read_only.parent), before)
        finally:
            read_only.parent.chmod(0o755)

    def test_changed_read_only_target_rejects_every_write(self) -> None:
        first = self.project / "AGENTS.md"
        second = self.project / "shared" / "CLAUDE.md"
        write_text(first, "First user instructions\n")
        write_text(second, "Second user instructions\n")
        before = tree_snapshot(self.project)
        with self.deny_directory_write(second.parent):
            with self.assertRaises(pensieve_core.InstructionSyncError) as error:
                pensieve_core.sync_instruction_targets(self.data_root, [first, second])
        self.assertIn("Preflight failed", str(error.exception))
        self.assertIn(str(second), str(error.exception))
        self.assertEqual(tree_snapshot(self.project), before)

    def test_parent_and_child_targets_reject_both_orders_without_writes(self) -> None:
        parent = self.project / "new-file"
        child = parent / "AGENTS.md"
        for targets in ([parent, child], [child, parent]):
            with self.subTest(targets=targets):
                before = tree_snapshot(self.project)
                arguments = [argument for target in targets for argument in ("--file", str(target))]
                result = self.run_script("sync-instructions.sh", "--client", "codex", *arguments, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("parent directory", result.stderr)
                self.assertIn("No instruction files were written", result.stderr)
                self.assertEqual(tree_snapshot(self.project), before)

    def test_parent_conflicts_are_checked_after_resolving_directory_links(self) -> None:
        actual = self.project / "actual"
        actual.mkdir()
        alias = self.project / "alias"
        alias.symlink_to(actual, target_is_directory=True)
        parent = actual / "new-file"
        child = alias / "new-file" / "AGENTS.md"
        before = tree_snapshot(self.project)
        with self.assertRaises(pensieve_core.InstructionSyncError):
            pensieve_core.sync_instruction_targets(self.data_root, [child, parent])
        self.assertEqual(tree_snapshot(self.project), before)

    def run_sync_python(self, target, popen):
        source = (SCRIPTS_ROOT / "sync-instructions.sh").read_text(encoding="utf-8")
        embedded = source.split("<<'SYNC_PY'\n", 1)[1].rsplit("\nSYNC_PY", 1)[0]
        output, errors = io.StringIO(), io.StringIO()
        arguments = ["-", str(SCRIPTS_ROOT), str(self.data_root), "codex", str(target)]
        with patch.object(sys, "argv", arguments), patch.object(sys, "path", list(sys.path)):
            with patch.object(subprocess, "Popen", popen):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                    exec(compile(embedded, str(SCRIPTS_ROOT / "sync-instructions.sh"), "exec"), {})
        return output.getvalue(), errors.getvalue()

    def test_marker_timeout_keeps_completed_files_and_terminates_process_group(self) -> None:
        target = self.project / "AGENTS.md"
        write_text(target, "User instructions\n")
        marker_state = tree_snapshot(self.data_root / ".state")
        process = MagicMock()
        process.__enter__.return_value = process
        process.pid = 123456
        process.wait.side_effect = [subprocess.TimeoutExpired("marker", 10), 0]
        popen = MagicMock(return_value=process)
        with patch.object(os, "killpg", create=True) as kill_group:
            output, errors = self.run_sync_python(target, popen)
        self.assertIn("sync completed", output)
        self.assertIn("timed out after 10 seconds", errors)
        self.assertIn(pensieve_core.INSTRUCTION_START, target.read_text())
        self.assertEqual(tree_snapshot(self.data_root / ".state"), marker_state)
        self.assertEqual(process.wait.call_args_list[0].kwargs, {"timeout": 10})
        self.assertEqual(popen.call_args.kwargs["start_new_session"], os.name == "posix")
        if os.name == "posix":
            kill_group.assert_called_once_with(process.pid, signal.SIGKILL)
            process.kill.assert_not_called()
        else:
            process.kill.assert_called_once_with()
            kill_group.assert_not_called()

    def test_marker_launch_or_exit_failure_does_not_fail_completed_sync(self) -> None:
        target = self.project / "AGENTS.md"
        process = MagicMock()
        process.__enter__.return_value = process
        process.wait.return_value = 1
        for popen in (MagicMock(side_effect=OSError("cannot launch marker")), MagicMock(return_value=process)):
            with self.subTest(popen=popen):
                write_text(target, "User instructions\n")
                output, errors = self.run_sync_python(target, popen)
                self.assertIn("sync completed", output)
                self.assertIn("session marker could not be refreshed", errors)
                self.assertIn(pensieve_core.INSTRUCTION_START, target.read_text())

    def test_unchanged_sync_does_not_launch_marker(self) -> None:
        target = self.project / "AGENTS.md"
        block = pensieve_core.instruction_block(pensieve_core.instruction_routes(self.data_root))
        write_text(target, block)
        before = tree_snapshot(self.project)
        popen = MagicMock()
        output, errors = self.run_sync_python(target, popen)
        self.assertIn("unchanged", output)
        self.assertEqual(errors, "")
        popen.assert_not_called()
        self.assertEqual(tree_snapshot(self.project), before)
