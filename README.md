# architecture-diagram-generator

A [Claude Code](https://claude.com/claude-code) plugin that analyzes a local repository and produces an architecture report, a Mermaid dependency diagram, and recommendations based on what the analysis found.

| Stack | What becomes a node | What becomes an edge |
|---|---|---|
| .NET | `.csproj` / `.fsproj` / `.vbproj` | `<ProjectReference>` |
| Node.js monorepo | each workspace package | dependency on another workspace package |
| Node.js / TypeScript single package | folders | imports (relative, tsconfig `baseUrl` / `paths`) |
| Python | distributions, or subpackages/modules of a single package | requirements / `import` statements |
| Maven / Gradle | modules / included projects | inter-module dependencies |

The analysis also checks for dependency cycles, projects outside the solution or workspace, unresolved references, and modules that no test imports.

## Install

In Claude Code:

```
/plugin marketplace add ythalorossy/architecture-diagram-generator
/plugin install architecture-diagram-generator@ythalorossy
```

To update later: `/plugin marketplace update ythalorossy`.

**Without the plugin system:** copy `skills/architecture-diagram-generator/` into `~/.claude/skills/`.

## Requirements

- Python 3.11+ (standard library only, no pip install needed)
- Optional: Node.js, to render the diagram to SVG via [`@mermaid-js/mermaid-cli`](https://github.com/mermaid-js/mermaid-cli) (`mmdc`, or fetched through `npx`). Without it, the report contains only the Mermaid source.

## Usage

Ask Claude, for example:

- *"Generate an architecture diagram for ~/src/my-repo"*
- *"Review the architecture of this repository"*
- *"How do the projects in this solution depend on each other?"*

The skill triggers on requests like these.

You can also run the analyzer directly:

```bash
python3 skills/architecture-diagram-generator/scripts/analyze_repository.py <repo_path> --output <output_dir>
```

Output files: `ArchitectureReport.md`, `dependency-graph.mmd` / `.svg` / `.json`, `repository-scan.json`, `summary.json`.

## Layout

```
.claude-plugin/            plugin and marketplace manifests
skills/architecture-diagram-generator/
  SKILL.md                 instructions Claude follows
  scripts/                 analyzer (one module per ecosystem)
  assets/                  report template, review checklist, and templates for the system-overview and per-service docs
```

## License

[MIT](LICENSE)
