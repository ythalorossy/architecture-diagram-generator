from pathlib import Path
import re


def _node_ids(names):
    """Mermaid IDs must be plain identifiers; the real names go in the labels."""
    ids = {}
    used = set()

    for name in names:
        base = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_") or "node"

        if base[0].isdigit():
            base = f"n_{base}"

        candidate = base
        suffix = 2

        while candidate in used:
            candidate = f"{base}_{suffix}"
            suffix += 1

        used.add(candidate)
        ids[name] = candidate

    return ids


def _label(text):
    return text.replace('"', "#quot;")


def generate_mermaid(graph, groups=None):
    """
    Render the dependency graph as a Mermaid flowchart.

    groups optionally maps a project name to a folder (e.g. src/Domain);
    projects sharing a folder are drawn inside one subgraph. Targets that are
    not keys of the graph (unresolved references) get a dashed border.
    """
    groups = groups or {}

    external = sorted({
        target
        for targets in graph.values()
        for target in targets
        if target not in graph
    })

    ids = _node_ids(list(graph) + external)

    by_group = {}

    for name in graph:
        by_group.setdefault(groups.get(name, ""), []).append(name)

    group_ids = _node_ids([
        f"group_{group}"
        for group in by_group
        if group
    ])

    lines = [
        "graph TD"
    ]

    for group, names in sorted(by_group.items()):
        indent = "    "

        if group:
            lines.append(
                f'    subgraph {group_ids[f"group_{group}"]}["{_label(group)}"]'
            )
            indent = "        "

        for name in names:
            lines.append(f'{indent}{ids[name]}["{_label(name)}"]')

        if group:
            lines.append("    end")

    for name in external:
        lines.append(f'    {ids[name]}["{_label(name)}"]')

    for source, targets in graph.items():
        for target in targets:
            lines.append(
                f"    {ids[source]} --> {ids[target]}"
            )

    if external:
        lines.append("    classDef external stroke-dasharray: 5 5")
        lines.append(
            "    class "
            + ",".join(ids[name] for name in external)
            + " external"
        )

    return "\n".join(lines) + "\n"


def render_svg(mermaid_file, svg_file, timeout=180):
    """
    Render a .mmd file to SVG with mermaid-cli, so the report can show the
    diagram as an image in viewers that don't render Mermaid (e.g. VS Code's
    built-in preview). Uses `mmdc` if installed, else `npx`. Returns True on
    success; any failure (no Node, no network, timeout) returns False.
    """
    import shutil
    import subprocess

    if shutil.which("mmdc"):
        command = ["mmdc"]
    elif shutil.which("npx"):
        command = ["npx", "-y", "@mermaid-js/mermaid-cli"]
    else:
        return False

    import json
    import tempfile

    # Plain <text> labels: HTML labels (<foreignObject>) go blank in some
    # viewers when the SVG is shown as an <img>.
    config = {
        "htmlLabels": False,
        "markdownAutoWrap": False,
        "flowchart": {"htmlLabels": False, "wrappingWidth": 1000}
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as file:
        json.dump(config, file)
        config_file = file.name

    try:
        result = subprocess.run(
            command + [
                "-i", str(mermaid_file),
                "-o", str(svg_file),
                "-c", config_file,
                "-b", "white"
            ],
            capture_output=True,
            timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    finally:
        Path(config_file).unlink(missing_ok=True)

    return result.returncode == 0 and Path(svg_file).is_file()


def save_mermaid(graph, output_file, groups=None):
    content = generate_mermaid(graph, groups)

    Path(output_file).write_text(
        content,
        encoding="utf-8"
    )


if __name__ == "__main__":
    import json
    import sys

    with open(sys.argv[1], encoding="utf-8") as file:
        graph = json.load(file)

    save_mermaid(
        graph,
        sys.argv[2] if len(sys.argv) > 2 else "dependency-graph.mmd"
    )
