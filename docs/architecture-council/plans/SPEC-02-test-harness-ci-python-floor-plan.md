# SPEC-02 Test harness, CI, Python 3.11 floor and CLI error UX — Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a fixture-based regression net and CI matrix, enforce Python 3.11+, and make both CLIs fail with actionable messages.
**Architecture:**
- Minimal per-ecosystem fixture repositories live under `tests/fixtures/` and drive detector, end-to-end and contract tests through the public entry points (`RepositoryAnalyzer.run`, `render_c4.render`, `validate`).
- A new `cli_support.py` holds the version guard and error formatting shared by both CLIs.
- CI is a single GitHub Actions workflow.

**Tech Stack:** Python 3.11+ stdlib, unittest (CI only: coverage, ruff)
**Spec:** specs/SPEC-02-test-harness-ci-python-floor.md

## Objective
Every module has tests, the Phase 2 failure modes are pinned, CI runs on 3.11–3.13 on Linux and Windows, and CLI errors are one-line and file-qualified.

## Global Constraints
- D1: 3.11 floor with a fail-fast guard.
- D6: stdlib runtime, with dev tools in CI only.
- D7: no code in this plan.
- Tests run with no network, Node.js or mmdc.
- Golden comparisons mask `run_id`, `Generated On` and absolute paths.

## Review Focus
1. Golden tests must mask volatile fields, or they will flap (REL-12).
2. The version guard must run before any import that needs 3.11 (`tomllib`), so it has to sit at the top of each CLI module.
3. `--debug` must not change exit codes.
4. Contract tests must assert "no traceback" (stderr has no `Traceback`), not just exit 1.
5. Windows: fixtures must not include symlinks or mode-000 files on Windows. Skip those tests with `skipUnless(os.name == "posix")`.

## Tasks
### Task 1: Fixture corpus and helpers
**Files:** Create `tests/fixtures/{dotnet_sln,maven_multi,gradle_kts,go_mod,node_workspace,python_dist,compose_poly}/…`. Modify `tests/helpers.py` (add `run_analyzer(fixture, tmp)` and `mask_volatile(json_obj)`).
- [x] Write failing test `test_helpers.MaskTest.test_masks_run_id_timestamp_and_abs_paths`, asserting the masked keys are replaced by placeholders.
- [x] Run `python3 -m unittest test_helpers` (from `tests/`); expect FAIL.
- [x] Implement the helpers in `tests/helpers.py`. Copy the fixtures from the Phase 2 scratch repros (`f-good`, `f-end`), trimmed to at most 10 files each.
- [x] Run the tests; expect PASS.
- [x] Commit `test: fixture corpus and analyzer test helpers`

### Task 2: Detector tests
**Files:** Create `tests/test_detectors.py`.
- [x] Write failing tests `test_dotnet_solution_projects_and_refs`, `test_maven_modules_and_deps`, `test_gradle_includes`, `test_go_packages`, `test_node_workspace_globs`, `test_python_distribution_requirements`. Each asserts the project names and edges from `build_dependency_graph(fixture)`.
- [x] Run `python3 -m unittest test_detectors`. Expect FAIL until the fixtures are complete, then PASS against the current behaviour, which is recorded as the baseline.
- [x] Commit `test: per-ecosystem detector baselines`

### Task 3: End-to-end golden tests
**Files:** Create `tests/test_analyze_e2e.py` and `tests/golden/<fixture>/{c4-facts.json,summary.json}`.
- [x] Write failing test `test_e2e_matches_golden[<fixture>]` (one per fixture, via `subTest`), asserting that the masked output equals the golden file.
- [x] Write `test_e2e_is_deterministic`, asserting two runs produce byte-identical masked outputs.
- [x] Generate the golden files once, review them by hand, and commit them.
- [x] Run the tests; expect PASS.
- [x] Commit `test: end-to-end golden outputs`

### Task 4: Validator contract cases (PE-11 Tier 0)
**Files:** Create `tests/test_validate_contract.py`.
- [x] Write the failing table-driven test `test_malformed_model_reports_error_not_traceback`, with cases: `bad_json`, `top_level_list`, `containers_str`, `system_str`, `element_str`, `excluded_without_id`, `flow_steps_str`, `components_list`. Each asserts `render()` returns `status == "invalid"` and an error mentioning `c4-model.json`. It currently fails, and SPEC-06 makes it pass. Mark it `expectedFailure` until SPEC-06 lands.
- [x] Write `test_reference_example_validates` (the PE-10 example passes render). Mark it `expectedFailure` until SPEC-01 lands.
- [x] Commit `test: validator contract cases (expected failures pending SPEC-06/01)`

### Task 5: Failure-mode tests (pending SPEC-03)
**Files:** Create `tests/test_failure_modes.py`.
- [x] Write `test_non_utf8_setup_cfg_does_not_abort`, `test_unreadable_dir_is_skipped` (posix only), and `test_outside_symlink_is_skipped` (posix only). Each asserts exit 0 and that a warning names the path. Mark them `expectedFailure` until SPEC-03.
- [x] Commit `test: pin REL-01/02 failure modes`

### Task 6: Version guard and CLI error UX
**Files:** Create `skills/c4-diagrams/scripts/cli_support.py`. Modify `analyze_repository.py` (`main`, `parse_arguments`) and `render_c4.py` (`main`). Test: `tests/test_cli.py`.
- [x] Write failing tests:
  - `test_version_guard_exits_1_with_hint` (patch `sys.version_info` to 3.10): stderr contains `Python 3.11+ is required` and `uv python install`.
  - `test_render_missing_facts_message`: exit 1, the message names `c4-facts.json`, no `Traceback`.
  - `test_unexpected_error_hint_and_debug`: without `--debug`, one line plus the hint; with `--debug`, the traceback is present.
- [x] Run `python3 -m unittest test_cli`; expect FAIL.
- [x] Implement in `cli_support.py`:
  - `require_python()`, called first in both CLIs before any 3.11-only import;
  - `UserError(message, path)`;
  - `run_cli(main_fn, debug)`, which formats a `UserError` as `ERROR: <path>: <message>` and any other exception as an internal error with a `--debug` hint.
  Add a `--debug` flag to both parsers. Raise `UserError` in `render_c4.render` when `c4-facts.json` is missing.
- [x] Run the tests; expect PASS.
- [x] Commit `feat(cli): Python 3.11 guard, file-qualified errors, --debug`

### Task 7: CI and lint
**Files:** Create `.github/workflows/ci.yml` and `pyproject.toml` (`[tool.ruff]` only).
- [x] Add jobs:
  - `test` matrix: python 3.11, 3.12, 3.13 × ubuntu-latest, windows-latest. It runs `python -m unittest discover -s tests`, plus `coverage run` and `coverage report` on ubuntu 3.12.
  - `lint`: `ruff check skills tests`.
  - `guard`: python 3.10 runs `analyze_repository.py --help` and asserts exit 1.
- [x] Push a branch; expect all jobs green except the intentional expected failures.
- [x] Commit `ci: unittest matrix 3.11-3.13 on linux/windows, ruff, version guard job`

### Task 8: Docs consistency
**Files:** Modify `README.md` (Python section, the 3.9/3.10 lines) and `skills/c4-diagrams/SKILL.md:5,48`.
- [x] State "Python 3.11+ (checked at startup)" in both places and remove the 3.9/3.10 claims. Document `python3 -m unittest discover -s tests`.
- [x] Commit `docs: single Python floor and test command`

## Dependencies
- None hard.
- SPEC-01, SPEC-03 and SPEC-06 flip the expected failures from Tasks 4–5.
- SPEC-09 defines `run_id`. Until then, mask by key name.
- SPEC-15 extends the ruff rules.

## Rollback Considerations
Tests and CI are additive and can be reverted freely. The version guard is the only runtime behaviour change: reverting `require_python()` calls restores the old behaviour. Keep it in a separate commit (Task 6).

## Validation Steps
1. `python3 -m unittest discover -s tests` → all pass (expected failures listed as `expected failures`).
2. `PATH=/usr/bin:/bin python3 skills/c4-diagrams/scripts/render_c4.py /tmp/empty` → exit 1, a single `ERROR:` line naming `c4-facts.json`.
3. `uv run --python 3.10 skills/c4-diagrams/scripts/analyze_repository.py .` → exit 1, `Python 3.11+ is required`.
4. GitHub Actions → `test (3.11–3.13 × ubuntu/windows)`, `lint` and `guard` are green.

## Implementation Outcome (2026-10-09)

All 8 tasks shipped on branch `spec-02-test-harness-ci` (11 commits ahead of `main @ 60a2404`); unmerged. Local test run: `Ran 75 tests in 38s — OK (expected failures=4)`. Coverage: 78% total, 6 of 7 Bar-B modules ≥ 70%, `code_facts.py` 69% (1 pp gap, AC2 PARTIAL). See `.serena/SPEC-02-audit.md` for per-AC evidence and `.serena/SPEC-02-final-report.md` for the full audit. CI workflow shipped in `.github/workflows/ci.yml` (matrix 3.11–3.13 × ubuntu/windows, lint, guard) but unobserved on `main`; the first push is the real test of AC5. Hand-off items for the next agent are listed in the spec's "Hand-off to the next agent" section.
