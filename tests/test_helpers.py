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
        # Masking must not mutate the input.
        self.assertEqual(
            sample["summary"]["output_folder"],
            "/tmp/abc/architecture-docs/bookshop",
        )


if __name__ == "__main__":
    unittest.main()