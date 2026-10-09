"""Tests for the shared test helpers in helpers.py."""
import unittest

from helpers import mask_volatile


class MaskTest(unittest.TestCase):
    def test_masks_run_id_timestamp_and_abs_paths(self):
        sample = {
            "repository": "bookshop",
            "summary": {
                "output_folder": "/tmp/abc/architecture-docs/bookshop",
                "nested": {"run_id": "abc-123"},
                "items": [
                    {"Generated On": "2026-01-01T00:00:00Z", "value": 1},
                    {"timestamp": "2026-01-01T00:00:00Z", "value": 2},
                ],
            },
            "untouched": "kept",
            "list": ["/abs/path", {"path": "/abs/other"}],
            "relative_with_home": "../../home/alice/work/repo",
            "relative_clean": "../../fixtures/repos/x",
            "repository_root": "../../home/alice/work/repo",
            "windows_output": r"C:\Users\runneradmin\AppData\Local\Temp\abc",
            "windows_drive_root": "D:/a/architecture-skills/repo",
            "mac_tmp": "/private/var/folders/abc/T/bookshop",
        }

        masked = mask_volatile(sample)

        # output_folder is replaced regardless of which dict holds it.
        self.assertEqual(masked["summary"]["output_folder"], "<abs-path>")
        # A run_id-style key is masked even though no run_id exists in the code yet.
        self.assertEqual(masked["summary"]["nested"]["run_id"], "<masked>")
        # Generated On and timestamp keys are masked by name.
        self.assertEqual(masked["summary"]["items"][0]["Generated On"], "<masked>")
        self.assertEqual(masked["summary"]["items"][0]["value"], 1)
        self.assertEqual(masked["summary"]["items"][1]["timestamp"], "<masked>")
        # Untouched fields survive.
        self.assertEqual(masked["untouched"], "kept")
        # Masking is recursive into lists of scalars and dicts.
        self.assertEqual(masked["list"][0], "<abs-path>")
        self.assertEqual(masked["list"][1]["path"], "<abs-path>")
        # A relative path that embeds an absolute home component is masked.
        self.assertEqual(masked["relative_with_home"], "<abs-path>")
        # A relative path that does not embed an absolute component survives.
        self.assertEqual(masked["relative_clean"], "../../fixtures/repos/x")
        # repository_root is masked by name (it is volatile in three
        # different ways depending on platform: home-embedded on POSIX,
        # clean ../../../... on Windows same-drive, drive-letter absolute
        # on Windows different-drive). All three must be replaced.
        self.assertEqual(masked["repository_root"], "<abs-path>")
        # Windows-style absolute paths (backslashes) are masked by value.
        self.assertEqual(masked["windows_output"], "<abs-path>")
        # Windows-style absolute paths (forward slashes, as_posix) are
        # masked by value, including non-C drives.
        self.assertEqual(masked["windows_drive_root"], "<abs-path>")
        # macOS /private/var/folders/... (Python's tempfile on macOS) is
        # masked by value because it embeds the user's account path.
        self.assertEqual(masked["mac_tmp"], "<abs-path>")
        # Masking must not mutate the input.
        self.assertEqual(
            sample["summary"]["output_folder"],
            "/tmp/abc/architecture-docs/bookshop",
        )
        self.assertEqual(
            sample["repository_root"],
            "../../home/alice/work/repo",
        )


if __name__ == "__main__":
    unittest.main()