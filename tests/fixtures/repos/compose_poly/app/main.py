"""Placeholder app source so the docker-compose fixture is not a bare folder.

The e2e golden treats compose_poly as a deployment-only repository: nothing
in `build_dependency_graph` recognises it, so the graph is empty by design.
This file exists only so the build context `./app` is real.
"""
def main():
    pass