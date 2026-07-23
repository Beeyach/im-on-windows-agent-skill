from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.py"


class InstallerTests(unittest.TestCase):
    def run_installer(self, home: Path, agent: str, *extra: str):
        return subprocess.run(
            [sys.executable, str(INSTALLER), "--home", str(home), "--agent", agent, *extra],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_installs_for_codex(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            result = self.run_installer(home, "codex")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((home / ".agents/skills/im-on-windows/SKILL.md").is_file())

    def test_installs_for_claude(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            result = self.run_installer(home, "claude")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((home / ".claude/skills/im-on-windows/SKILL.md").is_file())

    def test_refuses_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            self.assertEqual(self.run_installer(home, "codex").returncode, 0)
            result = self.run_installer(home, "codex")
            self.assertEqual(result.returncode, 2)
            self.assertIn("--force", result.stderr)

    def test_force_refuses_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            target = home / ".agents/skills/im-on-windows"
            target.mkdir(parents=True)
            (target / "important.txt").write_text("do not replace", encoding="utf-8")
            result = self.run_installer(home, "codex", "--force")
            self.assertEqual(result.returncode, 2)
            self.assertTrue((target / "important.txt").is_file())

    def test_force_updates_owned_install(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            self.assertEqual(self.run_installer(home, "both").returncode, 0)
            result = self.run_installer(home, "both", "--force")
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
