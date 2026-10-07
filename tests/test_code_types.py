import tempfile
import unittest

from helpers import line_of, write
from scripts import code_types


def extract_from(files, crlf=False):
    with tempfile.TemporaryDirectory() as tmp:
        return code_types.extract(write(tmp, files, crlf))


CS = '''using System;
namespace Acme.Workflow
{
    /// <summary>Moves jobs between states. Not a class { here }.</summary>
    public interface IWorkflowConductor
    {
        Task<bool> ChangeStatus(long jobId, short newStatus,
            string assignTo);
        bool IsValidTransition(short from, short to);
    }

    public abstract class RepositoryBase
    {
        protected string Sql = "select { from x";
        public Task<int> Execute(string sql) => null;
    }

    [Serializable] public class WorkflowConductor : RepositoryBase, IWorkflowConductor
    {
        private readonly IClock _clock;
        public WorkflowConductor(IClock clock, ILogger<WorkflowConductor> logger) { _clock = clock; }
        public async Task<bool> ChangeStatus(long jobId, short newStatus, string assignTo)
        {
            if (jobId > 0) { return true; }
            return false;
        }
        public bool IsValidTransition(short from, short to) => true;
        private void Audit() { }
        public List<Job> Jobs { get; set; }

        private class Nested { public void Hidden() { } }
    }

    public enum JobStatus { Ready = 10, Processing = 20, Complete }

    public interface IClock { DateTime Now(); }
    public partial class Job { public long Id { get; set; } }
}
'''

CS_PARTIAL = '''namespace Acme.Workflow
{
    public partial class Job : IAuditable
    {
        public void Close() { }
    }
}
'''


class CSharpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.types = extract_from({
            "Workflow.cs": CS,
            "Job.Partial.cs": CS_PARTIAL,
            "Reference.cs": "public class GeneratedClient { }",
            "Form1.Designer.cs": "public partial class Form1 { }",
        }, crlf=True)

    def test_top_level_types_only_and_generated_files_skipped(self):
        self.assertEqual(sorted(self.types), [
            "IClock", "IWorkflowConductor", "Job", "JobStatus", "RepositoryBase", "WorkflowConductor",
        ])

    def test_interface_members(self):
        t = self.types["IWorkflowConductor"]
        self.assertEqual(t["kind"], "interface")
        self.assertEqual(t["methods"], [
            "ChangeStatus(jobId, newStatus, assignTo) Task<bool>",
            "IsValidTransition(from, to) bool",
        ])
        self.assertEqual(t["line"], line_of(CS, "public interface IWorkflowConductor"))

    def test_class_base_interface_public_methods_and_dependencies(self):
        t = self.types["WorkflowConductor"]
        self.assertEqual(t["kind"], "class")
        self.assertEqual(t["bases"], ["RepositoryBase"])
        self.assertEqual(t["interfaces"], ["IWorkflowConductor"])
        self.assertEqual(t["methods"], [
            "ChangeStatus(jobId, newStatus, assignTo) Task<bool>",
            "IsValidTransition(from, to) bool",
        ])
        self.assertEqual(t["depends_on"], ["IClock", "Job"])

    def test_abstract_class_with_braces_in_strings(self):
        t = self.types["RepositoryBase"]
        self.assertEqual(t["kind"], "abstract")
        self.assertEqual(t["methods"], ["Execute(sql) Task<int>"])

    def test_enum_values(self):
        self.assertEqual(self.types["JobStatus"]["kind"], "enum")
        self.assertEqual(self.types["JobStatus"]["values"], ["Ready", "Processing", "Complete"])

    def test_partial_classes_are_merged(self):
        t = self.types["Job"]
        self.assertEqual(t["interfaces"], ["IAuditable"])
        self.assertEqual(t["methods"], ["Close() void"])
        self.assertEqual(t["file"].name, "Workflow.cs")

    def test_unbalanced_file_does_not_crash(self):
        types = extract_from({"Broken.cs": 'public class Broken : Base\n{\n    public void Run() {\n        var s = "unterminated;\n'})
        self.assertEqual(types["Broken"]["bases"], ["Base"])


if __name__ == "__main__":
    unittest.main()
