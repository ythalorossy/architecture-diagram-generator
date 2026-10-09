"""End-to-end golden tests for the analyzer.

The golden files under ``tests/golden/<fixture>/`` are produced by running
the analyzer on the matching fixture and masking volatile fields. The test
compares masked output to the golden, so absolute paths and any future
``run_id`` / timestamp fields do not make the comparison flake.

Masking is recursive into dicts and lists: ``mask_volatile`` in
``helpers.py`` replaces absolute path strings with ``<abs-path>`` and any
key named ``run_id`` / ``Generated On`` or containing ``timestamp`` with
``<masked>``.
"""
import json
import tempfile
import unittest
from pathlib import Path

from helpers import mask_volatile, run_analyzer


FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "repos"
GOLDEN_ROOT = Path(__file__).resolve().parent / "golden"

# One entry per AC3 ecosystem. Listed in a fixed order so the subTest
# iterations and the golden directory layout stay in lockstep.
FIXTURES = [
    "dotnet_sln",
    "maven_multi",
    "gradle_kts",
    "go_mod",
    "node_workspace",
    "python_dist",
    "compose_poly",
]


def _golden_pair(fixture_name):
    """Return ((expected_facts, expected_summary), tmp_path) for fixture."""
    golden_dir = GOLDEN_ROOT / fixture_name
    facts = json.loads((golden_dir / "c4-facts.json").read_text(encoding="utf-8"))
    summary = json.loads((golden_dir / "summary.json").read_text(encoding="utf-8"))
    return facts, summary


class AnalyzeE2ETest(unittest.TestCase):
    def test_e2e_matches_golden(self):
        for fixture_name in FIXTURES:
            with self.subTest(fixture=fixture_name):
                fixture = FIXTURES_ROOT / fixture_name
                with tempfile.TemporaryDirectory() as tmp:
                    facts, summary = run_analyzer(fixture, tmp)
                expected_facts, expected_summary = _golden_pair(fixture_name)
                self.assertEqual(mask_volatile(facts), expected_facts)
                self.assertEqual(mask_volatile(summary), expected_summary)

    def test_e2e_is_deterministic(self):
        for fixture_name in FIXTURES:
            with self.subTest(fixture=fixture_name):
                fixture = FIXTURES_ROOT / fixture_name
                with tempfile.TemporaryDirectory() as tmp1, \
                        tempfile.TemporaryDirectory() as tmp2:
                    facts1, summary1 = run_analyzer(fixture, tmp1)
                    facts2, summary2 = run_analyzer(fixture, tmp2)
                # Masking must produce byte-equal dicts across runs.
                self.assertEqual(
                    mask_volatile(facts1),
                    mask_volatile(facts2),
                    f"{fixture_name}: c4-facts.json not byte-identical between runs",
                )
                self.assertEqual(
                    mask_volatile(summary1),
                    mask_volatile(summary2),
                    f"{fixture_name}: summary.json not byte-identical between runs",
                )


if __name__ == "__main__":
    unittest.main()