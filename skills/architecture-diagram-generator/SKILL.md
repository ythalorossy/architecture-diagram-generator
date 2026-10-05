---
name: architecture-diagram-generator
description: Use when the user asks for architecture documentation, C4 diagrams, a dependency graph or diagram, an architecture review, or an explanation of how a repository's projects, packages or modules fit together. Works on local repository paths (.NET, Node.js/TypeScript, Python, Java Maven/Gradle).
---

# Architecture Diagram Generator

Turn a repository into C4 diagrams (system context, containers, components), an architecture report, and evidence-based recommendations.

## How the work is split

| Level | Shows | Comes from |
|---|---|---|
| 1 · System context | the system, the people using it, the external systems it talks to | **you**, in `c4-model.json` |
| 2 · Containers | what runs on its own (web API, web app, worker, CLI) and the data stores | the script finds them; you name and describe them |
| 3 · Components | inside each container: its projects or modules and their dependencies | the script, from the code |
| Appendix | every project/module and reference, tests included, plus the automated checks | the script |

The script does the parts that are objective, and every item it finds carries `file:line` evidence. You add the parts that need judgement (who uses the system, what each external system is for, descriptions). `render_c4.py` checks your model against the facts and draws all levels in one style.

### What the script detects

- **Containers:** .NET `Sdk.Web`/`Worker`/Functions/`Exe` projects; Python packages using FastAPI/Flask/Django/Streamlit/Gradio/MCP/Celery or declaring `[project.scripts]`; Node.js packages using Express/Nest/Next/React/Vue/MCP or declaring `bin`; Spring Boot/Quarkus/Micronaut modules; docker-compose `build:` services.
- **Data stores:** EF Core providers (`UseSqlServer`, `UseNpgsql`…), DB/cache/queue clients (`psycopg`, `pymongo`, `redis`, `lancedb`, `pg`, `mongoose`…), Maven drivers, docker-compose images (postgres, redis, mssql…).
- **External systems:** SDKs (Anthropic, OpenAI, AWS, Stripe…), URL hosts in files that use an HTTP client, and URL settings in `appsettings*.json` (one system per setting).
- **Components:** the dependency graph inside each container, without tests. For .NET, Maven, Gradle and monorepos, a container's components are the projects it references. For one Python or Node.js package, they're its modules or folders. In dense graphs, shortcut edges are hidden (A → C is left out when A → B → C is drawn). Containers with more than 20 components are split by folder.

## Step 1 — Run the analysis

```bash
python3 "<skill_base_directory>/scripts/analyze_repository.py" <repository_path>
```

- Run it from the user's current working directory. By default the files go to `./architecture-docs/<repository name>/` there, so the user can keep, commit or delete them. Pass `--output <directory>` only if the user named another location. Never write into the skill folder.
- It writes `c4-facts.json`, facts-only C4 diagrams (`c4-container.*`, `c4-component-*.*`), `ArchitectureReport.md`, `dependency-graph.*`, `repository-scan.json` and `summary.json`.
- Requires Python 3.11+ to read `pyproject.toml`.
- SVGs are rendered with `mmdc` or `npx @mermaid-js/mermaid-cli` and embedded in the report as images, so they show in any Markdown viewer. Without Node.js the report keeps only the Mermaid blocks. Tell the user if that happened.

## Step 2 — Read the facts and the code

Read `summary.json` and `c4-facts.json`. Then read enough code to answer what the facts can't:

- **Who uses it?** Look at controllers or routes, auth handlers, UI, CLI commands, README.
- **What is each external system for?** Open the evidence lines.
- **Is each fact real?** For example, a `requests` call in a one-off script isn't a system dependency, and `excluded` is the place for it.
- **What does each container and key component do?**

Treat the component graph as the source of truth for which components and edges exist.

## Step 3 — Write `c4-model.json` and draw

Write `c4-model.json` in the output folder, following `assets/c4-model-reference.md`. In short:

- cover every fact id, either as an element, in an element's `facts` list, or in `excluded` with a reason;
- data stores go in `containers` with `"type": "database"`;
- every element has `evidence`, or `"assumption": true`.

Then run:

```bash
python3 "<skill_base_directory>/scripts/render_c4.py" <output folder>
```

If it exits with errors, fix the model and run it again. It rewrites the C4 section of `ArchitectureReport.md` and the `c4-*.mmd`/`.svg` files.

If `c4-model.json` already exists from an earlier run, it was kept (and maybe edited by the user). Update it rather than rewriting it from scratch, and keep the user's wording.

## Step 4 — Report to the user

1. **What the system is**: 2–3 sentences, from the Context level.
2. **Diagrams**: the Context and Container Mermaid blocks inline, then list the component diagrams by file.
3. **Findings**: each tied to a concrete element, component, file or edge. Mark which came from the automated checks (appendix) and which are your judgement. For a cycle, name an import that causes it.
4. **Assumptions**: the elements you marked as assumptions, for the user to confirm.
5. **Recommendations**: only ones backed by a finding.
6. **Artifacts**: the output folder path. It's the user's to keep, commit, or delete (or add to `.gitignore`), and `c4-model.json` can be edited and re-rendered with `render_c4.py`.

For an architecture review, walk through `assets/architecture-review-checklist.md`. If the user wants a system overview or per-service docs, fill `assets/system-overview-template.md` / `assets/service-template.md` from what you found.

**If nothing was detected** (no containers and an empty graph, e.g. an unsupported stack): build the picture from the source yourself, write the model by hand, and tell the user the diagrams were derived manually rather than by the script.

## Common mistakes

| Mistake | Fix |
|---|---|
| Stopping after Step 1 | The facts-only diagrams have no people, no purposes and no Context level. Write the model. |
| Inventing people, external systems or flows | Only what code, config or docs support; mark the rest `"assumption": true`. |
| Reporting "0 projects, no concerns" as healthy | Empty graph = not analyzed. Analyze manually. |
| Calling the architecture healthy because the checks passed | The checks cover reference hygiene and cycles only. Say what you actually inspected. |
| Treating "outside solution/workspace" as dead code | Examples, fixtures and tooling are often standalone on purpose. Check before recommending deletion. |
| Inventing layers ("Controller → Service → Repository") the code doesn't have | Name only components and edges in the facts or that you saw in the code. |
| Writing output to a temp or scratchpad folder | The user can't find it later. Use the default `./architecture-docs/` or the location they named. |
