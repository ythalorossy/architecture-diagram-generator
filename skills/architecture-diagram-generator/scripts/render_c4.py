"""
Draw the C4 diagrams (context, container, component) from c4-facts.json and,
when present, the c4-model.json the agent writes on top of it.

    python3 render_c4.py <output folder> [--facts-only]

Writes c4-*.mmd / c4-*.svg into the output folder and replaces the C4 block of
ArchitectureReport.md. Exits with status 1 when c4-model.json does not match the
facts (missing elements, unknown ids), listing every problem.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import json
import re
import sys
import textwrap

SKILL_DIR = Path(__file__).resolve().parent.parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from scripts.generate_mermaid import _node_ids, render_svg


MAX_COMPONENTS = 20
ROW_WIDTH = 6
BLOCK_START = "<!-- c4:start -->"
BLOCK_END = "<!-- c4:end -->"

STYLES = [
    "classDef person fill:#08427b,stroke:#052e56,color:#ffffff",
    "classDef container fill:#1168bd,stroke:#0b4884,color:#ffffff",
    "classDef system fill:#1168bd,stroke:#0b4884,color:#ffffff",
    "classDef component fill:#85bbf0,stroke:#5d82a8,color:#000000",
    "classDef external fill:#999999,stroke:#6b6b6b,color:#ffffff",
    "classDef shared fill:#dbe9f6,stroke:#5d82a8,color:#000000,stroke-dasharray:4 3",
]


# ---------- model ----------

def facts_only_model(facts):
    """A model with no judgement in it: containers, stores and external systems as found."""
    containers = [
        {
            "id": c["id"], "name": c["name"], "technology": c["technology"],
            "description": c["kind"].replace("-", " ") if c["kind"] != "unknown" else "",
            "type": "container", "evidence": c["evidence"],
        }
        for c in facts["containers"]
    ] + [
        {
            "id": s["id"], "name": s["name"], "technology": s["technology"], "description": "",
            "type": "database", "evidence": s["evidence"],
        }
        for s in facts["data_stores"]
    ]
    externals = [
        {
            "id": e["id"], "name": e["name"],
            "description": e["technology"] if e["technology"] != e["name"] else "",
            "evidence": e["evidence"],
        }
        for e in facts["external_systems"]
    ]
    relationships = [
        {"from": user, "to": item["id"], "description": "Reads/writes" if kind == "store" else "Calls"}
        for kind, items in (("store", facts["data_stores"]), ("external", facts["external_systems"]))
        for item in items
        for user in item["used_by"]
    ]
    return {
        "system": {"name": facts["repository"], "description": ""},
        "people": [],
        "containers": containers,
        "external_systems": externals,
        "relationships": relationships,
        "components": {},
        "excluded": [],
        "_facts_only": True,
    }


def _covers(element):
    return element.get("facts") or [element["id"]]


def validate(model, facts):
    """Return (errors, warnings). Errors make the model unusable."""
    errors, warnings = [], []

    elements = {}
    for section in ("people", "containers", "external_systems"):
        for element in model.get(section) or []:
            if "id" not in element or "name" not in element:
                errors.append(f"{section}: every element needs an id and a name ({element})")
                continue
            if element["id"] in elements:
                errors.append(f"duplicate id: {element['id']}")
            elements[element["id"]] = section
            if not element.get("evidence") and not element.get("assumption"):
                warnings.append(f"{element['id']}: no evidence and not marked as an assumption")

    if model.get("system", {}).get("name") is None:
        errors.append("system.name is missing")

    covered = {fact for section in ("containers", "external_systems") for e in model.get(section) or [] for fact in _covers(e)}
    covered |= {item["id"] for item in model.get("excluded") or []}
    for kind in ("containers", "data_stores", "external_systems"):
        for fact in facts[kind]:
            if fact["id"] not in covered:
                errors.append(
                    f"{fact['id']} ({fact['name']}) was found in the code but is not in the model; "
                    "add it (or list it in `facts` of an element) or put it in `excluded` with a reason"
                )

    for relationship in model.get("relationships") or []:
        for end in ("from", "to"):
            if relationship.get(end) not in elements:
                errors.append(f"relationship {relationship.get('from')} -> {relationship.get('to')}: unknown id {relationship.get(end)!r}")

    for container_id, descriptions in (model.get("components") or {}).items():
        if elements.get(container_id) != "containers":
            errors.append(f"components: {container_id!r} is not a container id")

    return errors, warnings


# ---------- mermaid ----------

def _clean(text):
    return str(text).replace("`", "'").replace('"', "'").replace("<", "‹").replace(">", "›")


def _wrap(text, width=34):
    return "\n".join(textwrap.wrap(_clean(text), width)) if text else ""


def _label(name, kind, description=""):
    lines = [f"**{_clean(name)}**", f"[{_clean(kind)}]"]
    if description:
        lines.append(_wrap(description))
    return '"`' + "\n".join(lines) + '`"'


def _edge_label(description, technology=""):
    text = _wrap(description, 28) if description else ""
    if technology:
        text += ("\n" if text else "") + f"[{_clean(technology)}]"
    return f'|"`{text}`"|' if text else ""


class Diagram:
    def __init__(self):
        self.lines = []
        self.classes = {}
        self.ids = {}

    def id(self, key):
        if key not in self.ids:
            self.ids[key] = _node_ids(list(self.ids) + [key])[key]
        return self.ids[key]

    def node(self, key, label, cls, shape="rect", indent="    "):
        open_, close = {"rect": ("[", "]"), "db": ("[(", ")]"), "round": ("(", ")")}[shape]
        self.lines.append(f"{indent}{self.id(key)}{open_}{label}{close}")
        self.classes.setdefault(cls, []).append(self.id(key))

    def edge(self, source, target, label="", dashed=False):
        arrow = "-.->" if dashed else "-->"
        self.lines.append(f"    {self.id(source)} {arrow}{label} {self.id(target)}")

    def text(self, boundaries=()):
        out = ["---", "config:", "  layout: elk", "---", "flowchart TB"] + self.lines + ["    " + s for s in STYLES]
        for cls, ids in self.classes.items():
            out.append(f"    class {','.join(ids)} {cls}")
        for boundary in boundaries:
            out.append(f"    style {boundary} fill:none,stroke:#444444,stroke-dasharray:6 4")
        return "\n".join(out) + "\n"


def _element_node(diagram, element, section, indent="    "):
    if section == "people":
        diagram.node(element["id"], _label(element["name"], "Person", element.get("description")), "person", "round", indent)
    elif section == "external_systems":
        diagram.node(element["id"], _label(element["name"], "Software System", element.get("description")), "external", "rect", indent)
    else:
        kind = "Container" + (f": {element['technology']}" if element.get("technology") else "")
        shape = "db" if element.get("type") in ("database", "queue") else "rect"
        diagram.node(element["id"], _label(element["name"], kind, element.get("description")), "container", shape, indent)


def _merge_relationships(relationships):
    """One edge per (from, to): keep the first description, collect technologies."""
    merged = {}
    for r in relationships:
        key = (r["from"], r["to"])
        if key[0] == key[1]:
            continue
        if key not in merged:
            merged[key] = dict(r)
    return list(merged.values())


def context_diagram(model):
    d = Diagram()
    system = model["system"]
    inside = {c["id"] for c in model["containers"] if not c.get("external")}
    outside = {c["id"]: c for c in model["containers"] if c.get("external")}

    for person in model["people"]:
        _element_node(d, person, "people")
    d.node("__system__", _label(system["name"], "Software System", system.get("description")), "system")
    for external in model["external_systems"]:
        _element_node(d, external, "external_systems")
    for container in outside.values():
        d.node(container["id"], _label(container["name"], "Software System", container.get("description")), "external")

    lift = lambda node: "__system__" if node in inside else node
    edges = _merge_relationships([
        {**r, "from": lift(r["from"]), "to": lift(r["to"])} for r in model["relationships"]
    ])
    for r in edges:
        d.edge(r["from"], r["to"], _edge_label(r.get("description"), r.get("technology")))
    return d.text()


def container_diagram(model):
    d = Diagram()
    for person in model["people"]:
        _element_node(d, person, "people")

    boundary = d.id("__boundary__")
    d.lines.append(f'    subgraph {boundary}["`**{_clean(model["system"]["name"])}** [Software System]`"]')
    for container in model["containers"]:
        if not container.get("external"):
            _element_node(d, container, "containers", indent="        ")
    d.lines.append("    end")

    for container in model["containers"]:
        if container.get("external"):
            d.node(container["id"], _label(container["name"], "Software System", container.get("description")), "external")
    for external in model["external_systems"]:
        _element_node(d, external, "external_systems")

    for r in _merge_relationships(model["relationships"]):
        d.edge(r["from"], r["to"], _edge_label(r.get("description"), r.get("technology")))
    return d.text([boundary])


def _short_names(nodes):
    """Drop the dotted/slashed prefix every node shares (rag_docling.x -> x)."""
    split = {n: re.split(r"(?<=[./])", n) for n in nodes}
    dotted = [parts for parts in split.values() if len(parts) > 1]
    if len(dotted) < 2:
        return {n: n for n in nodes}
    prefix = []
    for column in zip(*dotted):
        if len(set(column)) != 1:
            break
        prefix.append(column[0])
    prefix = "".join(prefix)
    return {n: (n[len(prefix):] if prefix and n.startswith(prefix) and len(n) > len(prefix) else n) for n in nodes}


def _transitive_reduction(edges):
    def reachable(start, skip):
        seen, stack = set(), [t for t in edges.get(start, []) if (start, t) != skip]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack += edges.get(node, [])
        return seen

    return {a: [b for b in targets if b not in reachable(a, (a, b))] for a, targets in edges.items()}


def _component_views(container_fact):
    """
    Split one container's components into readable views: [(suffix, title, nodes, edges, notes)].
    Shortcut edges are hidden when the graph is dense; above MAX_COMPONENTS nodes the
    view is grouped by folder (one overview plus one view per folder), and modules
    most others use are moved to a "shared" box.
    """
    nodes = container_fact["components"]["nodes"]
    edges = container_fact["components"]["edges"]
    notes = []

    edge_count = sum(len(t) for t in edges.values())
    if edge_count > 1.5 * len(nodes):
        reduced = _transitive_reduction(edges)
        hidden = edge_count - sum(len(t) for t in reduced.values())
        if hidden:
            notes.append(
                f"{hidden} of {edge_count} dependencies are hidden because a longer path already shows them "
                "(A → C is left out when A → B → C is drawn). The full list is in the dependency graph appendix."
            )
            edges = reduced

    groups = {}
    for node, info in nodes.items():
        groups.setdefault(info["group"] or "(root)", []).append(node)

    if len(nodes) > MAX_COMPONENTS and len(groups) > 1:
        group_of = {n: (nodes[n]["group"] or "(root)") for n in nodes}
        group_edges = {}
        for source, targets in edges.items():
            for target in targets:
                a, b = group_of[source], group_of[target]
                if a != b:
                    group_edges.setdefault(a, set()).add(b)
        overview_nodes = {g: {"group": "", "label": f"{g} ({len(ns)})"} for g, ns in groups.items()}
        views = [("", "folders", overview_nodes, {g: sorted(t) for g, t in group_edges.items()},
                  notes + [f"{len(nodes)} components grouped by folder; each folder has its own diagram below."])]
        for group, members in sorted(groups.items()):
            if len(members) > 1:
                member_set = set(members)
                views.append((
                    "-" + re.sub(r"[^a-z0-9]+", "-", group.lower()).strip("-"),
                    group,
                    {n: nodes[n] for n in members},
                    {n: [t for t in edges.get(n, []) if t in member_set] for n in members},
                    [],
                ))
        return views

    shared = []
    if len(nodes) > MAX_COMPONENTS:
        indegree = {n: 0 for n in nodes}
        for targets in edges.values():
            for target in targets:
                indegree[target] += 1
        threshold = max(3, len(nodes) // 2)
        shared = [n for n, count in indegree.items() if count >= threshold]
        if shared:
            notes.append(
                "Used by most other components, drawn in the Shared box without their incoming edges: "
                + ", ".join(f"{n} ({indegree[n]})" for n in shared) + "."
            )
            edges = {n: [t for t in targets if t not in shared] for n, targets in edges.items()}
    if len(nodes) > MAX_COMPONENTS:
        notes.append(f"{len(nodes)} components: above the {MAX_COMPONENTS} that stay readable in one diagram.")

    return [("", "", {n: {**nodes[n], "shared": n in shared} for n in nodes}, edges, notes)]


def component_diagrams(model, facts):
    """[(file stem, title, mermaid, notes)] for every container with at least two components."""
    by_fact = {}
    for section in ("containers", "external_systems"):
        for element in model[section]:
            for fact in _covers(element):
                by_fact[fact] = element

    descriptions = model.get("components") or {}
    relationship_text = {(r["from"], r["to"]): r for r in model["relationships"]}
    results = []

    for container_fact in facts["containers"]:
        components = container_fact.get("components") or {}
        if len(components.get("nodes", {})) < 2:
            continue
        container = by_fact.get(container_fact["id"])
        if container is None:
            continue  # excluded in the model

        for suffix, subtitle, nodes, edges, notes in _component_views(container_fact):
            d = Diagram()
            short = _short_names(list(nodes))
            boundary = d.id("__boundary__")
            title = container["name"] + (f" / {subtitle}" if subtitle else "")
            d.lines.append(f'    subgraph {boundary}["`**{_clean(title)}** [Container]`"]')
            texts = descriptions.get(container["id"]) or {}
            regular = [n for n, info in nodes.items() if not info.get("shared")]
            shared = [n for n, info in nodes.items() if info.get("shared")]
            for node in regular:
                label = nodes[node].get("label") or short[node]
                d.node(node, _label(label, "Component", texts.get(node, "")), "component", indent="        ")
            if shared:
                d.lines.append(f'        subgraph {d.id("__shared__")}["Shared"]')
                for node in shared:
                    d.node(node, _label(short[node], "Component", texts.get(node, "")), "shared", indent="            ")
                d.lines.append("        end")
            d.lines.append("    end")

            for source, targets in edges.items():
                for target in targets:
                    d.edge(source, target)

            # ELK puts every top-level component in one row; invisible links
            # stack them in rows of ROW_WIDTH so wide diagrams stay readable.
            targeted = {t for targets in edges.values() for t in targets}
            roots = [n for n in regular if n not in targeted]
            for upper, lower in zip(roots, roots[ROW_WIDTH:]):
                d.lines.append(f"    {d.id(upper)} ~~~ {d.id(lower)}")

            # Data stores and external systems the components use.
            for kind in ("data_stores", "external_systems"):
                for fact in facts[kind]:
                    element = by_fact.get(fact["id"])
                    users = [n for n in fact["used_by_components"].get(container_fact["id"], []) if n in nodes]
                    if element is None or not users:
                        continue
                    if element["id"] not in d.ids:
                        section = "containers" if element in model["containers"] else "external_systems"
                        _element_node(d, element, section)
                    r = relationship_text.get((container["id"], element["id"]), {})
                    for user in users:
                        d.edge(user, element["id"], _edge_label(r.get("description", "Uses"), r.get("technology")))

            stem = f"c4-component-{container['id']}{suffix}"
            results.append((stem, title, d.text([boundary]), notes))

    return results


# ---------- output ----------

def _section(title, stem, mermaid, svg_ok, notes=()):
    lines = [title, ""]
    lines += [f"> {note}" for note in notes] + ([""] if notes else [])
    if svg_ok:
        lines += [f"![{stem}]({stem}.svg)", "", "<details>", "<summary>Mermaid source</summary>", "",
                  "```mermaid", mermaid.rstrip(), "```", "", "</details>"]
    else:
        lines += ["```mermaid", mermaid.rstrip(), "```"]
    return "\n".join(lines) + "\n"


def _assumptions(model):
    items = []
    for section in ("people", "containers", "external_systems"):
        for element in model.get(section) or []:
            if element.get("assumption"):
                items.append(f"- **{element['name']}**: {element.get('description') or 'no description'}")
    return items


def render(output_dir, facts_only=False, svg=True):
    output = Path(output_dir).resolve()
    facts = json.loads((output / "c4-facts.json").read_text(encoding="utf-8"))
    model_file = output / "c4-model.json"

    errors, warnings = [], []
    if facts_only or not model_file.is_file():
        model = facts_only_model(facts)
    else:
        model = json.loads(model_file.read_text(encoding="utf-8"))
        for key in ("people", "containers", "external_systems", "relationships", "excluded"):
            model.setdefault(key, [])
        errors, warnings = validate(model, facts)
        if errors:
            return {"errors": errors, "warnings": warnings}

    for old in list(output.glob("c4-*.mmd")) + list(output.glob("c4-*.svg")):
        old.unlink()

    diagrams = []
    if not model.get("_facts_only"):
        diagrams.append(("c4-context", "### Level 1: System context", context_diagram(model), []))
    if model["containers"]:
        diagrams.append(("c4-container", "### Level 2: Containers", container_diagram(model), []))
    for stem, title, mermaid, notes in component_diagrams(model, facts):
        diagrams.append((stem, f"#### {title}", mermaid, notes))

    for stem, _, mermaid, _ in diagrams:
        (output / f"{stem}.mmd").write_text(mermaid, encoding="utf-8")

    rendered = {}
    if svg:
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = {stem: pool.submit(render_svg, output / f"{stem}.mmd", output / f"{stem}.svg") for stem, *_ in diagrams}
            rendered = {stem: job.result() for stem, job in jobs.items()}

    block = [BLOCK_START, "## Architecture (C4 model)", ""]
    if model.get("_facts_only"):
        block += [
            "> Drawn from code facts only: no `c4-model.json` yet, so people, external purposes and "
            "descriptions are missing and the System Context level is left out. "
            "Write `c4-model.json` and run `render_c4.py` to complete it.", "",
        ]
    if not model["containers"]:
        block += ["> No containers, data stores or external systems were detected, so there are no C4 diagrams. "
                  "Build the model from the source by hand, or see the dependency graph appendix.", ""]
    elif model["system"].get("description") and not model.get("_facts_only"):
        block += [_clean(model["system"]["description"]), ""]

    component_header_done = False
    for stem, title, mermaid, notes in diagrams:
        if stem.startswith("c4-component") and not component_header_done:
            block += ["### Level 3: Components", ""]
            component_header_done = True
        block.append(_section(title, stem, mermaid, rendered.get(stem), notes))

    assumptions = _assumptions(model)
    if assumptions:
        block += ["### Assumptions", "", "Not backed by code evidence; confirm with the team:", ""] + assumptions + [""]

    block += ["### C4 files", ""] + [f"- [{stem}.mmd]({stem}.mmd)" for stem, *_ in diagrams]
    block += ["- [c4-facts.json](c4-facts.json)"] + (["- [c4-model.json](c4-model.json)"] if model_file.is_file() and not facts_only else [])
    block += [BLOCK_END]

    report = output / "ArchitectureReport.md"
    if report.is_file():
        text = report.read_text(encoding="utf-8")
        pattern = re.compile(re.escape(BLOCK_START) + ".*?" + re.escape(BLOCK_END), re.DOTALL)
        if pattern.search(text):
            report.write_text(pattern.sub(lambda _: "\n".join(block), text), encoding="utf-8")
        else:
            warnings.append("ArchitectureReport.md has no C4 block; re-run analyze_repository.py")

    return {
        "errors": [],
        "warnings": warnings,
        "diagrams": [stem for stem, *_ in diagrams],
        "svg_failed": [stem for stem, ok in rendered.items() if not ok] if svg else [],
        "facts_only": bool(model.get("_facts_only")),
    }


def main():
    parser = argparse.ArgumentParser(description="Draw the C4 diagrams from c4-facts.json and c4-model.json.")
    parser.add_argument("output", help="Output folder written by analyze_repository.py")
    parser.add_argument("--facts-only", action="store_true", help="Ignore c4-model.json and draw from the facts alone")
    parser.add_argument("--no-svg", action="store_true", help="Skip SVG rendering")
    args = parser.parse_args()

    result = render(args.output, facts_only=args.facts_only, svg=not args.no_svg)

    for warning in result["warnings"]:
        print(f"WARNING: {warning}")
    if result["errors"]:
        print("c4-model.json does not match c4-facts.json:", file=sys.stderr)
        for error in result["errors"]:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)

    print("Diagrams: " + ", ".join(result["diagrams"]))
    if result["svg_failed"]:
        print("WARNING: SVG rendering failed for " + ", ".join(result["svg_failed"]) + " (needs Node.js and @mermaid-js/mermaid-cli)")


if __name__ == "__main__":
    main()
