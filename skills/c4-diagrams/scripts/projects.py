from functools import lru_cache
from pathlib import Path

try:
    from scripts import dotnet_projects, node_projects, python_projects, java_projects, go_projects
except ImportError:
    import dotnet_projects, node_projects, python_projects, java_projects, go_projects


def _dotnet(repo):
    discovery = dotnet_projects.discover_projects(repo)
    for project in discovery["projects"]:
        project["ecosystem"] = ".NET"
        project["references"] = dotnet_projects.project_references(project["path"])
    return discovery


ECOSYSTEMS = (_dotnet, node_projects.discover_projects, python_projects.discover_projects, java_projects.discover_projects, go_projects.discover_projects)


@lru_cache(maxsize=8)
def discover_all(repo_path):
    """
    Projects from every supported ecosystem, in one shape:

    name, id (unique display name), path (unique key), relative_path, group,
    ecosystem, in_solution (False = outside every solution/workspace/aggregator,
    None = the ecosystem has no such list), duplicate_name, and references
    (paths of other projects, or plain names for references that did not resolve).
    """
    repo = Path(repo_path).resolve()

    solutions = []
    projects = []
    for discover in ECOSYSTEMS:
        discovery = discover(repo)
        solutions += discovery["solutions"]
        projects += discovery["projects"]

    dotnet_projects.assign_unique_names(projects)

    return {"solutions": solutions, "projects": projects}
