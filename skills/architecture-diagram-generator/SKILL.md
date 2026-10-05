---
name: architecture-diagram-generator
description: Use when the user asks for architecture documentation, a dependency graph or diagram, an architecture review, or an explanation of how a repository's projects, packages or modules fit together. Works on local repository paths (.NET, Node.js/TypeScript, Python, Java Maven/Gradle).
---

# Architecture Diagram Generator

Turn a repository into an architecture report, a Mermaid dependency diagram, and evidence-based recommendations.

## What the script draws

| Stack | Nodes | Edges | Extra checks |
|---|---|---|---|
| .NET | `.csproj`/`.fsproj`/`.vbproj` | `<ProjectReference>` | projects outside every `.sln`/`.slnx` |
| Node.js monorepo | each workspace `package.json` | dependencies naming another package | packages outside the workspace globs; `workspace:` deps that don't exist |
| Node.js single package | folders (descends into the folder holding most code, e.g. `src/app/*`) | imports: relative, tsconfig `baseUrl` and `paths` | — |
| Python, several distributions | each `pyproject.toml`/`setup.py`/`setup.cfg` | requirements naming another distribution | — |
| Python, one package | subpackages/modules (or top-level modules in a flat layout), plus `tests/` | `import` statements | production modules no test imports |
| Maven | each non-`pom` module | `<dependency>` on another module's artifactId | modules no aggregator lists |
| Gradle | each `include`d project | `project(':x')`, `projects.x` | `project(':x')` not in settings |

All stacks get cycle detection. Mixed repos produce one combined graph (the Components table has an Ecosystem column). Third-party dependencies are never drawn.

An empty graph (`dependency_graph_available: false` in `summary.json`) means "not analyzed", never "healthy".

## Step 1 — Run the analysis

```bash
python3 "<skill_base_directory>/scripts/analyze_repository.py" <repository_path> --output <output_directory>
```

- Always pass `--output`: your scratchpad, or a repo folder (e.g. `docs/architecture/`) only if the user asked to save docs there. Never write into the skill folder.
- Output: `ArchitectureReport.md`, `dependency-graph.mmd`, `dependency-graph.svg`, `dependency-graph.json`, `repository-scan.json`, `summary.json`.
- Requires Python 3.11+ to read `pyproject.toml`.
- The SVG is rendered with `mmdc` or `npx @mermaid-js/mermaid-cli` and embedded in the report as an image, so the diagram shows in any Markdown viewer (VS Code's built-in preview doesn't render Mermaid). Without Node.js the script prints a warning and the report keeps only the Mermaid block. Tell the user if that happened.

## Step 2 — Read the results

Read `summary.json`, then `ArchitectureReport.md` and `dependency-graph.mmd`. Treat the graph as the source of truth for which nodes and edges exist; don't add edges it doesn't contain.

Then open a few key nodes (entry points, the most-used node, each side of any cycle) to judge what the checks can't see: layer direction, misplaced responsibilities, oversized modules.

**If the graph is empty or a single node** (unsupported stack, or one tiny package): build the picture from the source yourself, and tell the user the diagram was derived manually rather than by the script.

**If the graph has 40+ nodes:** present a reduced diagram (group by the Folder column, or keep the most-connected nodes) and point to the full `.mmd` file.

## Step 3 — Report to the user

1. **Stack and shape**: what's there, in 2–3 sentences.
2. **Diagram**: the Mermaid block, inline.
3. **Findings**: each tied to a concrete node, file, or edge. Mark which came from the automated checks and which are your judgement. For a cycle, name an import that causes it.
4. **Recommendations**: only ones backed by a finding.
5. **Artifacts**: the output folder path.

For an architecture review, walk through `assets/architecture-review-checklist.md`. If the user wants a system overview or per-service docs, fill `assets/system-overview-template.md` / `assets/service-template.md` from what you found.

## Common mistakes

| Mistake | Fix |
|---|---|
| Reporting "0 projects, no concerns" as healthy | Empty graph = not analyzed. Analyze manually. |
| Calling the architecture healthy because the checks passed | The checks cover reference hygiene and cycles only. Say what you actually inspected. |
| Treating "outside solution/workspace" as dead code | Examples, fixtures and tooling are often standalone on purpose. Check before recommending deletion. |
| Inventing layers ("Controller → Service → Repository") the code doesn't have | Name only nodes and edges in the graph or that you saw in the code. |
| Writing output into the user's repo unasked | Use the scratchpad unless they named a location. |
