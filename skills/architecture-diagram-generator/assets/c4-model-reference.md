# c4-model.json reference

`c4-model.json` holds the parts of the C4 model that need judgement: who uses the system, what each external system is for, and a one-line description of every element. `render_c4.py` draws the diagrams from it, combined with the facts in `c4-facts.json`.

## Shape

```json
{ "note": "This example was removed. See the current version of this file for a complete, validating example." }
```

## Rules

- **Cover every fact.** Every `id` in `c4-facts.json` (`containers`, `data_stores`, `external_systems`) must appear in the model: as an element with the same `id`, in some element's `facts` list (to merge or rename facts), or in `excluded` with a reason. `render_c4.py` fails and lists any fact you missed.
- **Data stores are containers.** Put a database, cache or queue the system owns in `containers` with `"type": "database"` (or `"queue"`). A store the system doesn't own (a SaaS vector DB, another team's database) goes there too, with `"external": true`; it is then drawn outside the system boundary.
- **Evidence or assumption.** Give each person, container and external system `evidence` (repo-relative `file` or `file:line`), or mark it `"assumption": true`. Assumptions are listed in the report for the team to confirm. People are usually assumptions unless the code names them (auth roles, UI copy, README).
- **Don't invent.** Only add elements and relationships the code, config or docs support. When you have no evidence for who calls the API, say so with one `assumption` person rather than inventing several.
- **Relationship text** reads from → to: "Stores orders in", "Charges cards with". `technology` is the protocol or library (HTTPS, gRPC, EF Core, SQS).
- **`components`** (optional) gives a one-line description per component, keyed by container id and then the component id shown in `c4-facts.json` (`containers[].components.nodes`). The component nodes and edges themselves come from the code and can't be changed in the model.
- **Ids** are short kebab-case strings, unique across people, containers and external systems. Keep fact ids as they are so re-runs line up.

## Re-running

`analyze_repository.py` never overwrites `c4-model.json`. When the code changes, the facts are refreshed, and if the model no longer covers them the analyzer draws facts-only diagrams and prints `C4 MODEL ERROR` lines. Update the model, then run:

```bash
python3 "<skill_base_directory>/scripts/render_c4.py" <output folder>
```
