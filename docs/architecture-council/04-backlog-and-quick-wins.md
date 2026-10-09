# Phases 7–8 — Prioritized Backlog and Quick Wins

**Effort scale:**
- XS: under 1 hour
- S: under 1 day
- M: 1–5 days
- L: 1–2 weeks
- XL: more than 2 weeks

**Impact** is High, Medium or Low against the risk register (`03-technical-debt-and-risk.md`).

## Prioritized Backlog

| Rank | Pri | Spec | Title | Effort | Impact | Risks reduced | Hard dependencies | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | **P0** | SPEC-01 | Replace private-repo example with a synthetic, validating example | S (~1 d) | High (legal/confidentiality) | R-01 | — | shipped (in `60a2404`) |
| 2 | **P0** | SPEC-02 | Test harness, CI, Python 3.11 floor, CLI error UX | L (4–5 d) | High | R-04, R-14, T-1, T-5 | — | shipped (8/9 ACs; AC2 partial — `code_facts.py` 69%) on `spec-02-test-harness-ci` |
| 3 | **P0** | SPEC-04 | Single safe Mermaid emitter (ids and escaping) | M (2–3 d) | High | R-03, T-2 | SPEC-02 (soft) | pending — dependency now satisfied once SPEC-02 merges to `main` |
| 4 | **P0** | SPEC-06 | Validator robustness and tiered results | M (2–3 d) | High | R-05, P-2 | SPEC-02 (soft) | pending — dependency now satisfied |
| 5 | **P0** | SPEC-08 | Re-run semantics, degraded channel, relocatable output | M (~3 d) | High | R-05, A-2 | SPEC-06 | pending |
| 6 | **P0** | SPEC-03 | Shared repository index with tolerant I/O | M | High | R-02, R-06 | SPEC-02, SPEC-08 (skipped-files channel) | pending — SPEC-02 done; awaits SPEC-08 |
| 7 | P1 | SPEC-05 | Bounded, diagnosable SVG pipeline (pinned, offline-first, `--no-svg`) | M/L (3–4 d) | High | R-03, R-09 | SPEC-04 (soft) | pending |
| 8 | P1 | SPEC-12 | Unify compose parsing, store tables and test detection | M (~2 d) | High | R-10, M-1 | SPEC-02 | pending — SPEC-02 done; compose fixture is already in the corpus (`tests/fixtures/repos/compose_poly`) |
| 9 | P1 | SPEC-14 | Python discovery without manifests; requirements-only services | M (2–3 d) | Medium | R-10 | soft: SPEC-02, SPEC-03, SPEC-09, SPEC-12 | pending |
| 10 | P1 | SPEC-11 | Fact-collection performance and `collect_facts` decomposition | L (4–5 d) | High | R-06, M-2, T-4 | SPEC-02, SPEC-03 | pending — SPEC-02 done |
| 11 | P1 | SPEC-09 | Versioned facts, model and summary contracts | L (~5 d) | High | R-05, TD-04 | SPEC-02, SPEC-06 (its typed-records task should land before SPEC-11 Tasks 2–3 and SPEC-12; otherwise they rebase) | pending — SPEC-02 done; AC3 of SPEC-02 already masks `run_id` defensively pending SPEC-09 |
| 12 | P1 | SPEC-07 | Model contract enforcement (anti-hallucination) | M (~3 d) | High | R-07 | SPEC-06, SPEC-08 (tiers) | pending |
| 13 | P1 | SPEC-16 | Agent workflow quality: recall, determinism, facts brief, trigger | M (~3 d) | High | R-08, R-13, R-18 | SPEC-09 (soft, brief in summary) | pending |
| 14 | P1 | SPEC-10 | Atomic output writes and report ownership | M (~3 d) | Medium | R-12, TD-08 | SPEC-08 | pending |
| 15 | P1 | SPEC-19 | Single-source version, release automation, changelog, manifest generation | M (2–3 d) | Medium | R-11 | — | pending |
| 16 | P2 | SPEC-18 | Diagram semantics: reduction order, split edges, legend, shared libraries | L (4–6 d) | Medium | Output quality | SPEC-04 | pending |
| 17 | P2 | SPEC-13 | Layered packages, per-layer registries, unique package name | XL (~8 d, 4 milestones) | Medium | R-15, A-1 | SPEC-02, SPEC-03, SPEC-09 | pending — SPEC-02 done |
| 18 | P2 | SPEC-17 | Skill evaluation suite (trigger plus end-to-end gold fixtures) | L (~5 d) | Medium | P-1, R-07, R-08 | SPEC-01, SPEC-02 | pending — both deps done |
| 19 | P2 | SPEC-20 | Contributor docs: CONTRIBUTING, ARCHITECTURE, ecosystem guide, docstrings | M (~2 d) | Medium | R-17 | SPEC-02 (test cmd); update after SPEC-13 | pending — SPEC-02 done; the test command `python3 -m unittest discover -s tests` is already documented in `README.md:162` |
| 20 | P2 | SPEC-21 | User docs: limitations, troubleshooting, example output, README restructure | M (2–3 d) | Medium | R-14, R-17 | SPEC-01, SPEC-17 (bookshop example), SPEC-05 (SVGs); SPEC-14 soft | pending |
| 21 | P3 | SPEC-15 | Code hygiene: dead code, nesting, magic values, linter rules | M (2–3 d) | Low | M-3 | SPEC-02 | pending — SPEC-02 done; current ruff config is the minimal `E9/F63/F7/F82` set; SPEC-15 will extend it |

**Why P0 is this set.** It covers the confidentiality leak, the safety net every later change depends on, and the three defects that make the tool produce **nothing**, **broken diagrams**, or **silently lose the user's work** on ordinary repositories.

### Recommended delivery waves

| Wave | Specs (can run in parallel inside a wave) | Exit gate |
|---|---|---|
| 0 (day 1) | SPEC-01, quick wins below | Private names gone from `main`; quick wins merged | shipped |
| 1 | SPEC-02 | CI green on 3.11–3.13; golden e2e fixtures in place | shipped on `spec-02-test-harness-ci`; CI unobserved until first merge to `main` |
| 2 | SPEC-04, SPEC-06, SPEC-12, SPEC-14, SPEC-19, SPEC-11 Task 1 (OwnershipIndex) | All keyword-id fixtures parse; malformed models never trace back; perf budget for the 50-package chain met | pending |
| 3 | SPEC-08, SPEC-05, SPEC-09 | Re-run keeps the model; `summary.json` status and degraded channel; offline render fails fast; versioned contracts | pending |
| 4 | SPEC-03, SPEC-10, SPEC-07, SPEC-16, SPEC-11 Tasks 2–3 | No crash on hostile-filesystem fixtures; atomic outputs; tiered contract rules; brief in `summary.json` | pending |
| 5 | SPEC-13, SPEC-18, SPEC-17, SPEC-20, SPEC-21, SPEC-15 | Import-direction test passes; eval baseline recorded; docs match code | pending |

SPEC-13's package-move milestone needs a short merge freeze: land it after SPEC-11, SPEC-12 and SPEC-15 have merged or paused. SPEC-13 also refines ARC-03 by putting `contract` below `discovery`.

Each spec that changes output carries a CHANGELOG entry (SPEC-19), and its version bump is batched per wave: wave 2 ships 3.3.0, and wave 3 ships 4.0.0 (contract versioning, SPEC-09).

## Phase 8 — Quick Wins and sizing buckets

### Quick wins (under 1 hour each; most are the first task of their spec)

| # | Action | Spec | Finding | Status |
|---|---|---|---|---|
| QW-1 | Replace the private names, paths and line numbers in `assets/c4-model-reference.md` with a neutral synthetic example (the full validating example follows in SPEC-01) | SPEC-01 | PE-10 | shipped |
| QW-2 | Add a recall instruction to SKILL.md: add relationships and elements the scanner missed, *with evidence* | SPEC-16 | PE-06 | pending |
| QW-3 | Add negative scope to the SKILL.md `description` (not for quick "what does X import" questions) and add the flow, deployment and API intents | SPEC-16 | PE-08 | pending |
| QW-4 | Fix the `#` double-escape in `render_c4._seq_text` and escape `;` | SPEC-04 | DIA-06 | pending |
| QW-5 | Add a Python ≥ 3.11 fail-fast check with install hints to both CLIs | SPEC-02 | REL-13, DOC-08 | shipped (in `cli_support.py:require_python`) |
| QW-6 | Document `python3 -m unittest discover -s tests` in the README | SPEC-20 | DOC-03 | shipped (in `README.md:162`) |
| QW-7 | Fix the analyzer's "no supported projects" warning (add Go) and the SKILL.md H1 that still uses the old name | SPEC-19 | DOC-05 | pending |
| QW-8 | Remove dead code and the duplicated dict key | SPEC-15 | CQ-12 | pending |
| QW-9 | `_merge_relationships`: warn on duplicate pairs instead of dropping silently | SPEC-18 | DIA-10 | pending |
| QW-10 | Pass mmdc stderr into the warning instead of "needs Node.js" | SPEC-05 | REL-07/DIA-02 | pending |
| QW-11 | Owner action: create the missing `v3.0.1` and `v3.1.0` tags | SPEC-19 | DOC-01 | pending |

### Small improvements (under 1 day)

SPEC-01 (about 1 day), and these first slices: SPEC-11 Task 1 (the ARC-01 `OwnershipIndex` with an equivalence test, about 1 day), SPEC-04's keyword-id fix for DIA-01, and SPEC-19's CHANGELOG plus tag backfill.

### Medium improvements (under 1 week)

SPEC-02 (4–5 d), SPEC-03, SPEC-04, SPEC-05, SPEC-06, SPEC-07, SPEC-08, SPEC-09, SPEC-10, SPEC-12, SPEC-15, SPEC-16, SPEC-18 (4–6 d), SPEC-19, SPEC-20, SPEC-21.

### Strategic initiatives (more than 1 week elapsed, including review and stabilisation)

- **SPEC-11** (full): `collect_facts` decomposition into a `FactsContext` plus per-fact collectors.
- **SPEC-13**: layered packages, per-layer ecosystem registries, unique package name. This makes the repo a real multi-skill platform.
- **SPEC-17**: skill evaluation suite with gold fixtures, trigger precision/recall and run-to-run determinism.

**Total estimated effort:** about 60–75 engineer-days for all 21 specs, or about 6–8 calendar weeks with the 5–7 person team in `05-execution-team.md` working the waves in parallel. P0 alone is about 15–18 engineer-days.
