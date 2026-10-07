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


GO_TYPES = '''package store

import "context"

// Store is backed by Postgres. type Fake struct {}
type Store interface {
	Get(ctx context.Context, id string) (*Order, error)
	Put(ctx context.Context, o *Order) error
}

type Order struct {
	ID    string
	Lines []Line
}

type Line struct{ SKU string }

type PostgresStore struct {
	Base
	db     *DB
	clock  Clock
	prefix string // "{"
}

type Base struct{}
type DB struct{}
type Clock interface{ Now() int64 }
'''

GO_METHODS = '''package store

func (s *PostgresStore) Get(ctx context.Context, id string) (*Order, error) {
	if id == "" { return nil, nil }
	return &Order{}, nil
}

func (s *PostgresStore) Put(ctx context.Context, o *Order) error { return nil }

func (s *PostgresStore) close() {}

func NewPostgresStore(db *DB) *PostgresStore { return &PostgresStore{db: db} }
'''


class GoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.types = extract_from({"store.go": GO_TYPES, "store_methods.go": GO_METHODS})

    def test_types(self):
        self.assertEqual(sorted(self.types), ["Base", "Clock", "DB", "Line", "Order", "PostgresStore", "Store"])

    def test_interface_method_set(self):
        t = self.types["Store"]
        self.assertEqual(t["kind"], "interface")
        self.assertEqual(t["methods"], ["Get(ctx, id) (*Order, error)", "Put(ctx, o) error"])
        self.assertEqual(self.types["Clock"]["methods"], ["Now() int64"])

    def test_struct_fields_embedding_and_methods_from_another_file(self):
        t = self.types["PostgresStore"]
        self.assertEqual(t["kind"], "struct")
        self.assertEqual(t["embeds"], ["Base"])
        self.assertEqual(t["depends_on"], ["Clock", "DB"])
        self.assertEqual(t["methods"], ["Get(ctx, id) (*Order, error)", "Put(ctx, o) error"])
        self.assertEqual(self.types["Order"]["depends_on"], ["Line"])


PYTHON = '''from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class Notifier(ABC):
    """Sends things. class Fake: pass"""

    @abstractmethod
    def send(self, message: "Message") -> bool:
        ...


class SlackNotifier(Notifier):
    def __init__(self, client: "SlackClient", retries: int = 3):
        self.client = client

    def send(self, message, *, urgent=False) -> bool:
        def inner():
            pass
        return True

    async def flush(self):
        pass

    def _format(self, message):
        return ""


@dataclass
class Message:
    text: str
    channel: "Channel"


class Channel(Enum):
    GENERAL = "general"
    ALERTS = "alerts"


class SlackClient:
    pass
'''


class PythonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.types = extract_from({"notify.py": PYTHON, "notify_pb2.py": "class Generated:\n    pass\n"})

    def test_types(self):
        self.assertEqual(sorted(self.types), ["Channel", "Message", "Notifier", "SlackClient", "SlackNotifier"])

    def test_abstract_base(self):
        t = self.types["Notifier"]
        self.assertEqual(t["kind"], "abstract")
        self.assertEqual(t["bases"], [])
        self.assertEqual(t["methods"], ["send(message) bool"])

    def test_class_public_methods_and_init_dependencies(self):
        t = self.types["SlackNotifier"]
        self.assertEqual(t["bases"], ["Notifier"])
        self.assertEqual(t["methods"], ["send(message, urgent) bool", "flush()"])
        self.assertEqual(t["depends_on"], ["SlackClient"])

    def test_dataclass_and_enum(self):
        self.assertEqual(self.types["Message"]["kind"], "record")
        self.assertEqual(self.types["Message"]["depends_on"], ["Channel"])
        self.assertEqual(self.types["Channel"]["kind"], "enum")
        self.assertEqual(self.types["Channel"]["values"], ["GENERAL", "ALERTS"])


TYPESCRIPT = """import { Injectable } from '@nestjs/common';

/** class Fake {} */
export interface PaymentGateway {
  charge(amount: number, token: string): Promise<Receipt>;
  refund(id: string): Promise<void>;
}

export abstract class BaseGateway {
  protected readonly name = 'base {';
  abstract describe(): string;
}

@Injectable()
export class StripeGateway extends BaseGateway implements PaymentGateway {
  #secret = '';
  constructor(private readonly client: StripeClient, private logger: Logger) {
    super();
  }

  async charge(amount: number, token: string): Promise<Receipt> {
    if (amount > 0) { return { id: '1' } as Receipt; }
    throw new Error('x');
  }

  public refund(id: string): Promise<void> { return Promise.resolve(); }
  describe(): string { return 'stripe'; }
  private audit(): void {}
  protected log(): void {}
}

export enum Currency { USD = 'usd', EUR = 'eur' }

export interface Receipt { id: string; }
export class StripeClient {}
"""

JAVASCRIPT = """export default class Widget extends Base {
  render() { return 1; }
  #hidden() {}
}
"""


class TypeScriptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.types = extract_from({"payments.ts": TYPESCRIPT, "widget.js": JAVASCRIPT, "api.d.ts": "export interface Declared {}"})

    def test_types(self):
        self.assertEqual(sorted(self.types), [
            "BaseGateway", "Currency", "PaymentGateway", "Receipt", "StripeClient", "StripeGateway", "Widget",
        ])

    def test_interface_methods(self):
        t = self.types["PaymentGateway"]
        self.assertEqual(t["kind"], "interface")
        self.assertEqual(t["methods"], ["charge(amount, token) Promise<Receipt>", "refund(id) Promise<void>"])
        self.assertEqual(self.types["Receipt"]["methods"], [])

    def test_class_public_methods_and_constructor_dependencies(self):
        t = self.types["StripeGateway"]
        self.assertEqual(t["bases"], ["BaseGateway"])
        self.assertEqual(t["interfaces"], ["PaymentGateway"])
        self.assertEqual(t["methods"], ["charge(amount, token) Promise<Receipt>", "refund(id) Promise<void>", "describe() string"])
        self.assertEqual(t["depends_on"], ["StripeClient"])

    def test_abstract_enum_and_javascript(self):
        self.assertEqual(self.types["BaseGateway"]["kind"], "abstract")
        self.assertEqual(self.types["BaseGateway"]["methods"], ["describe() string"])
        self.assertEqual(self.types["Currency"]["values"], ["USD", "EUR"])
        self.assertEqual(self.types["Widget"]["bases"], ["Base"])
        self.assertEqual(self.types["Widget"]["methods"], ["render()"])


if __name__ == "__main__":
    unittest.main()
