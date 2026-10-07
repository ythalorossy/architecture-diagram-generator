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


JAVA = '''package com.acme.orders;

import java.util.List;

/** An order service. class Fake {} */
public interface OrderService {
    Order place(String customerId, List<Item> items);
    default void ping() { }
}

public abstract class BaseService {
    protected final String name = "base { name";
    public abstract String describe();
}

@Service
public class DefaultOrderService extends BaseService implements OrderService, Auditable {
    private final OrderRepository repository;
    private Clock clock;

    public DefaultOrderService(OrderRepository repository, Clock clock) {
        this.repository = repository;
    }

    @Override
    public Order place(String customerId,
                       List<Item> items) {
        if (items.isEmpty()) { throw new IllegalArgumentException(); }
        return null;
    }

    public String describe() { return "orders"; }
    private void audit() { }

    static class Inner { public void hidden() { } }
}

enum Status { NEW, PAID, SHIPPED; public boolean done() { return false; } }

interface OrderRepository { Order save(Order order); }
record Order(String id, List<Item> items) { }
class Item { }
'''


class JavaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.types = extract_from({"Orders.java": JAVA})

    def test_types(self):
        self.assertEqual(sorted(self.types), [
            "BaseService", "DefaultOrderService", "Item", "Order", "OrderRepository", "OrderService", "Status",
        ])

    def test_interface_with_default_method(self):
        t = self.types["OrderService"]
        self.assertEqual(t["kind"], "interface")
        self.assertEqual(t["methods"], ["place(customerId, items) Order", "ping() void"])

    def test_class_extends_implements_and_dependencies(self):
        t = self.types["DefaultOrderService"]
        self.assertEqual(t["bases"], ["BaseService"])
        self.assertEqual(t["interfaces"], ["OrderService", "Auditable"])
        self.assertEqual(t["methods"], ["place(customerId, items) Order", "describe() String"])
        self.assertEqual(t["depends_on"], ["OrderRepository"])
        self.assertEqual(t["line"], line_of(JAVA, "public class DefaultOrderService"))

    def test_abstract_enum_and_record(self):
        self.assertEqual(self.types["BaseService"]["kind"], "abstract")
        self.assertEqual(self.types["BaseService"]["methods"], ["describe() String"])
        self.assertEqual(self.types["Status"]["values"], ["NEW", "PAID", "SHIPPED"])
        self.assertEqual(self.types["Order"]["kind"], "record")
        self.assertEqual(self.types["Order"]["depends_on"], ["Item"])


KOTLIN = '''package com.acme.billing

interface InvoiceSender {
    fun send(invoice: Invoice): Boolean
}

abstract class BaseSender(protected val name: String) {
    abstract fun describe(): String
}

class EmailSender(
    private val client: MailClient,
    val template: String = "hi {name}",
) : BaseSender("email"), InvoiceSender {
    override fun send(invoice: Invoice): Boolean {
        return client.post(invoice.id)
    }
    override fun describe(): String = "email"
    private fun log(message: String) { }
    internal fun debug() { }
}

data class Invoice(val id: String, val lines: List<Line>)

enum class Currency { USD, EUR }

class MailClient { fun post(id: String): Boolean = true }
class Line
'''


class KotlinTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.types = extract_from({"Billing.kt": KOTLIN})

    def test_types(self):
        self.assertEqual(sorted(self.types), [
            "BaseSender", "Currency", "EmailSender", "Invoice", "InvoiceSender", "Line", "MailClient",
        ])

    def test_class_with_multiline_primary_constructor(self):
        t = self.types["EmailSender"]
        self.assertEqual(t["bases"], ["BaseSender"])
        self.assertEqual(t["interfaces"], ["InvoiceSender"])
        self.assertEqual(t["methods"], ["send(invoice) Boolean", "describe() String"])
        self.assertEqual(t["depends_on"], ["MailClient"])

    def test_kinds(self):
        self.assertEqual(self.types["InvoiceSender"]["methods"], ["send(invoice) Boolean"])
        self.assertEqual(self.types["BaseSender"]["kind"], "abstract")
        self.assertEqual(self.types["Invoice"]["kind"], "record")
        self.assertEqual(self.types["Invoice"]["depends_on"], ["Line"])
        self.assertEqual(self.types["Currency"]["values"], ["USD", "EUR"])
        self.assertEqual(self.types["MailClient"]["methods"], ["post(id) Boolean"])
        self.assertEqual(self.types["Line"]["kind"], "class")


if __name__ == "__main__":
    unittest.main()
