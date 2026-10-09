"""
REL-01 and REL-02 failure-mode pins (Task 5).

These tests pin behaviour that SPEC-03 will fix: today the analyzer either
exits non-zero or silently follows paths it should warn about. After SPEC-03
the analyzer will exit 0 and emit a warning that includes the path of the
offending file or directory. Until then, all three tests are marked
@unittest.expectedFailure so they show up as `xfail` in the test output
(honest bookkeeping — see the directive in the team-lead's brief).

The mode-000 directory and the outside-pointing symlink are built at runtime
inside `tempfile.TemporaryDirectory()` — they are NEVER committed to the
repository. Committing a mode-000 directory or an outside-symlink would break
the Windows-latest checkouts required by AC5 (git stores only the executable
bit, and an outside-pointing symlink fails on Windows outright). See A-9 in
`.serena/SPEC-02-traceability.md` for the full reasoning.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
ANALYZE = REPO / "skills" / "c4-diagrams" / "scripts" / "analyze_repository.py"


def _run_analyzer(repo, out):
    """Run the analyzer on `repo` with output to `out` (no SVG)."""
    return subprocess.run(
        [sys.executable, str(ANALYZE), str(repo), "--output", str(out), "--no-svg"],
        capture_output=True,
        text=True,
    )


class FailureModesTest(unittest.TestCase):
    """REL-01 (non-UTF-8 setup.cfg), REL-02 (mode-000 / outside symlink).
    All three are pinned as `expectedFailure` until SPEC-03 flips them."""

    @unittest.expectedFailure
    def test_non_utf8_setup_cfg_does_not_abort(self):
        """REL-01: a non-UTF-8 setup.cfg must be skipped with a warning,
        not abort the whole run. Today this crashes inside
        scripts.python_projects._read_setup_cfg with UnicodeDecodeError, which
        `run_cli` reports as an internal-error line and exits 1."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            # A Python project so setup.cfg is parsed.
            (repo / "pkg").mkdir()
            (repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
            # Non-UTF-8 bytes mid-file — invalid start byte 0xff.
            (repo / "setup.cfg").write_bytes(b"[metadata]\nname = b\xff\xfenomer\n")
            out = Path(tmp) / "out"

            proc = _run_analyzer(repo, out)
            combined = proc.stdout + proc.stderr

            self.assertEqual(
                proc.returncode, 0,
                f"REL-01: analyzer must exit 0 when only setup.cfg is bad; "
                f"got {proc.returncode}\nstderr: {proc.stderr}",
            )
            self.assertIn(
                "setup.cfg", combined,
                f"REL-01: a warning must name setup.cfg; got:\n{combined}",
            )

    @unittest.skipUnless(os.name == "posix", "POSIX-only: chmod 000 directory")
    @unittest.expectedFailure
    def test_unreadable_dir_is_skipped(self):
        """REL-02: a mode-000 subdirectory must be skipped with a warning,
        not raise through the analyzer. Today this raises PermissionError
        inside scan_repo / dotnet_projects and exits 1.

        The mode is restored in `finally` so `TemporaryDirectory.cleanup`
        can remove the parent dir."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            unreadable = repo / "no_access"
            unreadable.mkdir()
            # The detector tries to read files inside, so seed with one.
            (unreadable / "pyvenv.cfg").write_text("", encoding="utf-8")
            os.chmod(unreadable, 0)
            out = Path(tmp) / "out"

            try:
                proc = _run_analyzer(repo, out)
                combined = proc.stdout + proc.stderr
                self.assertEqual(
                    proc.returncode, 0,
                    f"REL-02: analyzer must exit 0 when a subdir is mode 000; "
                    f"got {proc.returncode}\nstderr: {proc.stderr}",
                )
                self.assertIn(
                    "no_access", combined,
                    f"REL-02: a warning must name no_access; got:\n{combined}",
                )
            finally:
                os.chmod(unreadable, 0o755)

    @unittest.skipUnless(os.name == "posix", "POSIX-only: symlinks")
    @unittest.expectedFailure
    def test_outside_symlink_is_skipped(self):
        """REL-02: a symlink pointing outside the repo must be skipped with
        a warning, not silently scanned. Today the analyzer follows the
        symlink (or skips it silently); SPEC-03 makes it emit a warning
        naming the symlink path."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()
            (outside / "leak.py").write_text("y = 2\n", encoding="utf-8")
            link = repo / "leak"
            link.symlink_to(outside)
            out = Path(tmp) / "out"

            proc = _run_analyzer(repo, out)
            combined = proc.stdout + proc.stderr

            self.assertEqual(
                proc.returncode, 0,
                f"REL-02: analyzer must exit 0; got {proc.returncode}\n"
                f"stderr: {proc.stderr}",
            )
            self.assertIn(
                "leak", combined,
                f"REL-02: a warning must name the symlink path 'leak'; "
                f"got:\n{combined}",
            )


if __name__ == "__main__":
    unittest.main()