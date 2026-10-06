from pathlib import Path
import json

try:
    from scripts.dotnet_projects import walk_files
except ImportError:
    from dotnet_projects import walk_files


def _uses_react(package_json):
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False

    dependencies = {
        **data.get("dependencies", {}),
        **data.get("devDependencies", {}),
        **data.get("peerDependencies", {})
    }

    return "react" in dependencies


def detect_stack(repo_path):
    repo = Path(repo_path)

    indicators = {
        ".NET": (".sln", ".slnx", ".csproj", ".fsproj", ".vbproj"),
        "Node.js": ("package.json",),
        "Python": ("requirements.txt", "pyproject.toml", "setup.py"),
        "Java": ("pom.xml", "build.gradle", "build.gradle.kts"),
        "Go": ("go.mod",)
    }

    # One pass over the tree (build and dependency folders are skipped).
    files = list(walk_files(
        repo,
        lambda name: name.endswith(sum(indicators.values(), ()))
    ))

    found = [
        stack
        for stack, suffixes in indicators.items()
        if any(file.name.endswith(suffixes) for file in files)
    ]

    # package.json alone does not mean React; check the dependencies.
    if any(
        file.name == "package.json" and _uses_react(file)
        for file in files
    ):
        found.append("React")

    return found


if __name__ == "__main__":
    import sys

    repo_path = sys.argv[1]

    stacks = detect_stack(repo_path)

    if stacks:
        print("Detected:")
        for stack in stacks:
            print(f" - {stack}")
    else:
        print("Unknown stack")
