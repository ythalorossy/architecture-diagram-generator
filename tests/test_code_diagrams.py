import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import write
from scripts import code_diagrams

WORKFLOW = '''namespace Api.Workflow;
public interface IWorkflowConductor { bool Change(long id); }
public abstract class RepositoryBase { }
public class WorkflowConductor : RepositoryBase, IWorkflowConductor
{
    public WorkflowConductor(IClock clock) { }
    public bool Change(long id) => true;
}
public interface IClock { long Now(); }
public class Unrelated { }
'''


def make_repo(root):
    write(root / "repo", {
        "Api/Api.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>',
        "Api/Program.cs": "var app = 1;\n",
        "Api/Workflow/Workflow.cs": WORKFLOW,
        "Api/Workflow/WorkflowTests.cs": "public class WorkflowTests { }",
    })


FACTS = {
    "repository_root": "../repo",
    "containers": [{
        "id": "api", "name": "Api", "path": "Api",
        "components": {"nodes": {"Api": {"path": "Api/Api.csproj", "group": "Api"}}, "edges": {"Api": []}},
        "code_components": {"nodes": {"Api::(root)": {}, "Api::Workflow": {}}, "edges": {}},
    }],
}


def model(*code):
    return {"containers": [{"id": "api", "name": "Api"}], "code": list(code)}


class PrepareTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_repo(self.root)
        self.output = self.root / "out"
        self.output.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def prepare(self, *code, facts=FACTS):
        return code_diagrams.prepare(model(*code), facts, self.output)

    def test_valid_entry_with_types(self):
        errors, warnings, entries = self.prepare(
            {"container": "api", "component": "Api::Workflow", "description": "Workflow", "types": ["WorkflowConductor"]})
        self.assertEqual((errors, warnings), ([], []))
        entry = entries[0]
        self.assertEqual(entry["stem"], "c4-code-api-api-workflow")
        self.assertEqual(entry["title"], "Api · Api::Workflow")
        self.assertEqual(entry["chosen"], ["WorkflowConductor", "IClock", "IWorkflowConductor", "RepositoryBase"])
        self.assertEqual(entry["left_out"], ["Unrelated"])
        self.assertNotIn("WorkflowTests", entry["types"])

    def test_module_component_reads_every_folder(self):
        errors, _, entries = self.prepare({"container": "api", "component": "Api"})
        self.assertEqual(errors, [])
        self.assertIn("WorkflowConductor", entries[0]["types"])

    def test_unknown_container(self):
        errors, _, _ = self.prepare({"container": "web", "component": "Api::Workflow"})
        self.assertIn("not a container", errors[0])

    def test_unknown_component_suggests_close_ids(self):
        errors, _, _ = self.prepare({"container": "api", "component": "Api::Workflw"})
        self.assertIn("did you mean Api::Workflow", errors[0])

    def test_unknown_type_suggests_close_names(self):
        errors, _, _ = self.prepare({"container": "api", "component": "Api::Workflow", "types": ["WorkflowConducter"]})
        self.assertIn("did you mean WorkflowConductor", errors[0])

    def test_missing_fields(self):
        errors, _, _ = self.prepare({"container": "api"})
        self.assertIn("needs a container and a component", errors[0])

    def test_component_without_types_is_a_warning(self):
        errors, warnings, entries = self.prepare({"container": "api", "component": "Api::(root)"})
        self.assertEqual((errors, entries), ([], []))
        self.assertIn("no classes or interfaces", warnings[0])

    def test_more_than_five_entries_warns(self):
        components = ["Api::Workflow", "Api", "Api::Workflow", "Api", "Api::Workflow", "Api"]
        _, warnings, _ = self.prepare(*[{"container": "api", "component": c} for c in components])
        self.assertTrue(any("Level 4 is meant for" in w for w in warnings))

    def test_duplicate_entries(self):
        errors, _, _ = self.prepare({"container": "api", "component": "Api"}, {"container": "api", "component": "Api"})
        self.assertIn("listed twice", errors[0])

    def test_facts_from_an_older_version(self):
        facts = {k: v for k, v in FACTS.items() if k != "repository_root"}
        errors, _, _ = self.prepare({"container": "api", "component": "Api"}, facts=facts)
        self.assertEqual(errors, ["code: c4-facts.json has no repository_root; re-run analyze_repository.py"])

    def test_no_code_entries_need_no_repository_root(self):
        facts = {k: v for k, v in FACTS.items() if k != "repository_root"}
        self.assertEqual(code_diagrams.prepare({"containers": []}, facts, self.output), ([], [], []))


class RepositoryRootTest(unittest.TestCase):
    def test_relative_with_forward_slashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            output = repo / "architecture-docs" / "repo"
            output.mkdir(parents=True)
            self.assertEqual(code_diagrams.repository_root(repo, output), "../..")

    def test_absolute_when_no_relative_path_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("os.path.relpath", side_effect=ValueError("path is on mount 'D:'")):
                self.assertEqual(code_diagrams.repository_root(tmp, tmp), Path(tmp).resolve().as_posix())


def fake(name, depends_on=(), methods=()):
    return {"name": name, "kind": "class", "bases": [], "interfaces": [], "embeds": [],
            "depends_on": list(depends_on), "methods": list(methods), "values": []}


class SelectTypesTest(unittest.TestCase):
    def test_large_component_draws_the_most_connected(self):
        types = {f"T{i:02}": fake(f"T{i:02}") for i in range(30)}
        types["Hub"] = fake("Hub", depends_on=[f"T{i:02}" for i in range(5)])
        chosen, left_out = code_diagrams.select_types(types)
        self.assertEqual(len(chosen), 12)
        self.assertEqual(chosen[:6], ["Hub", "T00", "T01", "T02", "T03", "T04"])
        self.assertEqual(len(left_out), 19)

    def test_wanted_types_come_first_even_when_unconnected(self):
        types = {"A": fake("A", depends_on=["B"]), "B": fake("B"), "C": fake("C")}
        chosen, left_out = code_diagrams.select_types(types, ["C", "A"])
        self.assertEqual(chosen, ["C", "A", "B"])
        self.assertEqual(left_out, [])
