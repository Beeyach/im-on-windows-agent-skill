from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "scripts" / "windows_mode.py"
SPEC = importlib.util.spec_from_file_location("windows_mode", SCRIPT)
assert SPEC and SPEC.loader
windows_mode = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(windows_mode)


class PathTests(unittest.TestCase):
    def test_classifies_windows_drive(self):
        self.assertEqual(windows_mode.path_style(r"C:\Users\Ary\project"), "windows-drive")

    def test_classifies_wsl_mount(self):
        self.assertEqual(windows_mode.path_style("/mnt/c/Users/Ary/project"), "wsl-mounted-drive")

    def test_classifies_wsl_unc(self):
        self.assertEqual(
            windows_mode.path_style(r"\\wsl.localhost\Ubuntu\home\ary\project"),
            "wsl-unc",
        )

    def test_windows_path_to_wsl(self):
        self.assertEqual(
            windows_mode.convert_path(r"C:\Users\Ary\My App", "wsl"),
            "/mnt/c/Users/Ary/My App",
        )

    def test_wsl_mount_to_windows(self):
        self.assertEqual(
            windows_mode.convert_path("/mnt/d/work/project", "windows"),
            r"D:\work\project",
        )

    def test_wsl_linux_path_to_unc(self):
        self.assertEqual(
            windows_mode.convert_path("/home/ary/project", "windows", "Ubuntu"),
            r"\\wsl.localhost\Ubuntu\home\ary\project",
        )

    def test_windows_executable_inside_wsl_is_classified(self):
        self.assertEqual(
            windows_mode.classify_tool("/mnt/c/Program Files/nodejs/node.exe"),
            "windows-from-wsl",
        )


class CommandTests(unittest.TestCase):
    def check(self, command: str, shell: str, cwd: str = r"C:\work\app"):
        return windows_mode.check_command(command, shell, cwd)

    def test_project_script_is_safe_in_powershell(self):
        self.assertEqual(self.check("npm test", "powershell")["status"], "safe")

    def test_rm_rf_is_blocked_in_powershell(self):
        self.assertEqual(self.check("rm -rf node_modules", "powershell")["status"], "blocked")

    def test_dev_null_is_blocked_in_powershell(self):
        self.assertEqual(self.check("npm test 2>/dev/null", "powershell")["status"], "blocked")

    def test_inline_env_is_blocked_in_powershell(self):
        self.assertEqual(self.check("NODE_ENV=test npm test", "powershell")["status"], "blocked")

    def test_and_chain_requires_review_in_powershell(self):
        self.assertEqual(self.check("npm test && npm run build", "powershell")["status"], "review")

    def test_powershell_cmdlet_is_blocked_in_cmd(self):
        self.assertEqual(self.check("Get-ChildItem .", "cmd")["status"], "blocked")

    def test_windows_drive_is_blocked_in_wsl(self):
        self.assertEqual(
            self.check(r"node C:\work\app\script.js", "wsl", "/home/ary/app")["status"],
            "blocked",
        )

    def test_powershell_is_blocked_in_wsl(self):
        self.assertEqual(
            self.check("Get-Process node", "wsl", "/home/ary/app")["status"],
            "blocked",
        )

    def test_wsl_mount_is_blocked_in_native_git_bash(self):
        with patch.dict(
            os.environ,
            {"WINDOWS_MODE_TEST_PLATFORM": "windows", "WINDOWS_MODE_TEST_WSL": "0"},
            clear=False,
        ):
            result = self.check("node /mnt/c/work/app.js", "bash")
        self.assertEqual(result["status"], "blocked")

    def test_wsl_unc_in_powershell_requires_review(self):
        result = self.check("npm test", "powershell", r"\\wsl.localhost\Ubuntu\home\ary\app")
        self.assertEqual(result["status"], "review")


class ProbeTests(unittest.TestCase):
    def test_probe_respects_explicit_shell(self):
        result = windows_mode.probe(".", "powershell")
        self.assertEqual(result["shell"], "powershell")

    def test_probe_flags_mounted_drive_in_wsl(self):
        with patch.dict(
            os.environ,
            {
                "WINDOWS_MODE_TEST_PLATFORM": "linux",
                "WINDOWS_MODE_TEST_WSL": "1",
                "WINDOWS_MODE_TEST_PATH": "/mnt/c/work/app",
            },
            clear=False,
        ):
            result = windows_mode.probe(".", "wsl")
        self.assertEqual(result["environment"], "wsl")
        self.assertTrue(result["risks"])


class CliTests(unittest.TestCase):
    def run_check(self, command: str):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "check",
                "--shell",
                "powershell",
                "--cwd",
                r"C:\work\app",
                "--",
                command,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_cli_safe_exit_code(self):
        result = self.run_check("npm test")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["status"], "safe")

    def test_cli_review_exit_code(self):
        result = self.run_check("npm test && npm run build")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "review")

    def test_cli_blocked_exit_code(self):
        result = self.run_check("rm -rf dist")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
