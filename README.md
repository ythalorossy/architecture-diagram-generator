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

| Tool | Required? | Version | Used for |
|---|---|---|---|
| [Claude Code](https://claude.com/claude-code) | Yes | any recent | runs the skill |
| Python | Yes | **3.11+** | the analyzer (standard library only, no `pip install`) |
| Node.js | Optional | **22.13+** | rendering the diagram to SVG with [`@mermaid-js/mermaid-cli`](https://github.com/mermaid-js/mermaid-cli) |

**You don't need the toolchain of the repository you analyze.** The analyzer only reads files (`.csproj`, `package.json`, `pyproject.toml`, `pom.xml`, `settings.gradle`, source imports). You can analyze a .NET or Java repository without the .NET SDK, a JDK, Maven or Gradle installed, and you don't need to run `npm install` first.

### Python

Check your version:

```bash
python3 --version
```

- **3.11 or newer**: fully supported.
- **3.9 / 3.10**: runs, but cannot read `pyproject.toml` (it needs `tomllib`, added in 3.11), so Python repositories are analyzed incompletely. The script prints a warning when this happens.
- **3.8 or older**: not supported.

If your system Python is older, install a newer one with your package manager, [python.org](https://www.python.org/downloads/), or `uv python install 3.12`.

> **Windows:** the skill calls `python3`. If only `python` or `py` is on your PATH, install Python from python.org or the Microsoft Store, which provides `python3`, or ask Claude to use `py -3`.

### Node.js and mermaid-cli (optional, for the SVG)

The report embeds `dependency-graph.svg` so the diagram shows in any Markdown viewer, including VS Code's built-in preview, which doesn't render Mermaid. The analyzer uses `mmdc` if it's on your PATH, and otherwise falls back to `npx -y @mermaid-js/mermaid-cli`.

Install mermaid-cli once, globally:

```bash
node --version          # must be 22.13 or newer
npm install -g @mermaid-js/mermaid-cli
mmdc --version
```

Installing it ahead of time is recommended. With the `npx` fallback, the first run downloads mermaid-cli and a headless Chrome (a few hundred MB), which can exceed the analyzer's 3-minute render timeout.

Without Node.js the analysis still works. The report then contains only the Mermaid source, and the script prints a warning.

> **Linux / WSL:** headless Chrome needs some system libraries. If `mmdc` fails with an error such as `error while loading shared libraries: libnss3.so`, install the packages listed in [Puppeteer's troubleshooting guide](https://pptr.dev/troubleshooting#chrome-doesnt-launch-on-linux) for your distribution.

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
