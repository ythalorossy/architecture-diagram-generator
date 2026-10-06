"""
Facts for the C4 diagrams: what a script can find without judgement.

- containers: things that run on their own (web API, web app, worker, CLI,
  function), found from project files and dependencies;
- data_stores: databases, caches, queues and vector stores the code connects to;
- external_systems: third-party APIs reached through an SDK or an HTTP client;
- components: per container, the projects/modules it is built from and the
  edges between them (the dependency graph, minus tests).

Every item carries `evidence` (repo-relative file:line) so the C4 model the agent
writes on top of it can be checked. People and the purpose of each element
are left to that model.
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from scripts.dotnet_projects import walk_files, local_tag, is_ignored_dir
    from scripts.projects import discover_all
    from scripts.python_projects import _distributions, normalize, _python_files
    from scripts.generate_docs import is_test_project
except ImportError:
    from dotnet_projects import walk_files, local_tag, is_ignored_dir
    from projects import discover_all
    from python_projects import _distributions, normalize, _python_files
    from generate_docs import is_test_project


SOURCE_EXTENSIONS = (".cs", ".fs", ".vb", ".py", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".java", ".kt")
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "e2e"}
MAX_EVIDENCE = 3


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "item"


# ---------- signals ----------

# (dependency or import name, kind, technology). First match wins per kind.
PYTHON_CONTAINER_SIGNALS = [
    ("fastapi", "web-api", "FastAPI"), ("flask", "web-api", "Flask"), ("django", "web-api", "Django"),
    ("starlette", "web-api", "Starlette"), ("aiohttp", "web-api", "aiohttp"), ("sanic", "web-api", "Sanic"),
    ("streamlit", "web-app", "Streamlit"), ("gradio", "web-app", "Gradio"), ("dash", "web-app", "Dash"),
    ("mcp", "mcp-server", "MCP SDK"), ("fastmcp", "mcp-server", "FastMCP"),
    ("celery", "worker", "Celery"), ("rq", "worker", "RQ"), ("dramatiq", "worker", "Dramatiq"),
    ("typer", "cli", "Typer"), ("click", "cli", "Click"),
]

NODE_CONTAINER_SIGNALS = [
    ("next", "web-app", "Next.js"), ("nuxt", "web-app", "Nuxt"), ("@angular/core", "web-app", "Angular"),
    ("react", "web-app", "React"), ("vue", "web-app", "Vue"), ("svelte", "web-app", "Svelte"),
    ("@nestjs/core", "web-api", "NestJS"), ("express", "web-api", "Express"), ("fastify", "web-api", "Fastify"),
    ("koa", "web-api", "Koa"), ("hono", "web-api", "Hono"),
    ("@modelcontextprotocol/sdk", "mcp-server", "MCP SDK"),
    ("electron", "desktop-app", "Electron"),
]

JAVA_CONTAINER_SIGNALS = [
    ("spring-boot-starter-web", "web-api", "Spring Boot"), ("spring-boot-starter-webflux", "web-api", "Spring WebFlux"),
    ("quarkus", "web-api", "Quarkus"), ("micronaut", "web-api", "Micronaut"),
    ("spring-boot", "app", "Spring Boot"),
]

# Code patterns (regex over source text) -> (kind, technology). kind is "store" or "external".
CODE_SIGNALS = [
    # .NET
    (r"\bUseSqlServer\s*\(|\bnew\s+SqlConnection\s*\(", "store", "SQL Server"),
    (r"\bUseNpgsql\s*\(|\bnew\s+NpgsqlConnection\s*\(", "store", "PostgreSQL"),
    (r"\bUseMySql\s*\(|\bUseMySQL\s*\(", "store", "MySQL"),
    (r"\bUseSqlite\s*\(", "store", "SQLite"),
    (r"\bUseCosmos\s*\(|\bnew\s+CosmosClient\s*\(", "store", "Azure Cosmos DB"),
    (r"\bnew\s+MongoClient\s*\(", "store", "MongoDB"),
    (r"\bConnectionMultiplexer\.Connect|\bAddStackExchangeRedisCache\s*\(", "store", "Redis"),
    (r"\bnew\s+Elastic(search)?Client\s*\(", "store", "Elasticsearch"),
    (r"\bnew\s+BlobServiceClient\s*\(", "store", "Azure Blob Storage"),
    (r"\bnew\s+ServiceBusClient\s*\(", "store", "Azure Service Bus"),
    (r"\bnew\s+AmazonS3Client\s*\(", "store", "Amazon S3"),
]

# Imported module / package name -> (kind, technology) for Python and Node.js.
IMPORT_SIGNALS = {
    # Python
    "psycopg": ("store", "PostgreSQL"), "psycopg2": ("store", "PostgreSQL"), "asyncpg": ("store", "PostgreSQL"),
    "pymysql": ("store", "MySQL"), "MySQLdb": ("store", "MySQL"), "pyodbc": ("store", "SQL Server"), "pymssql": ("store", "SQL Server"),
    "sqlite3": ("store", "SQLite"), "pymongo": ("store", "MongoDB"), "motor": ("store", "MongoDB"),
    "redis": ("store", "Redis"), "elasticsearch": ("store", "Elasticsearch"),
    "lancedb": ("store", "LanceDB"), "chromadb": ("store", "Chroma"), "qdrant_client": ("store", "Qdrant"),
    "pinecone": ("store", "Pinecone"), "pika": ("store", "RabbitMQ"), "kafka": ("store", "Kafka"),
    "anthropic": ("external", "Anthropic API"), "openai": ("external", "OpenAI API"),
    "google.generativeai": ("external", "Google Gemini API"), "google.genai": ("external", "Google Gemini API"),
    "boto3": ("external", "AWS"), "stripe": ("external", "Stripe"), "twilio": ("external", "Twilio"),
    "sendgrid": ("external", "SendGrid"), "slack_sdk": ("external", "Slack API"),
    # Node.js
    "pg": ("store", "PostgreSQL"), "postgres": ("store", "PostgreSQL"), "mysql": ("store", "MySQL"),
    "mysql2": ("store", "MySQL"), "mssql": ("store", "SQL Server"), "tedious": ("store", "SQL Server"),
    "mongodb": ("store", "MongoDB"), "mongoose": ("store", "MongoDB"), "ioredis": ("store", "Redis"),
    "sqlite3": ("store", "SQLite"), "better-sqlite3": ("store", "SQLite"),
    "@elastic/elasticsearch": ("store", "Elasticsearch"), "kafkajs": ("store", "Kafka"), "amqplib": ("store", "RabbitMQ"),
    "@anthropic-ai/sdk": ("external", "Anthropic API"), "@google/generative-ai": ("external", "Google Gemini API"),
    "@aws-sdk": ("external", "AWS"), "aws-sdk": ("external", "AWS"), "@sendgrid/mail": ("external", "SendGrid"),
    "@slack/web-api": ("external", "Slack API"),
    "@sentry/node": ("external", "Sentry"), "@sentry/react": ("external", "Sentry"), "sentry_sdk": ("external", "Sentry"),
    "applicationinsights": ("external", "Azure Application Insights"), "dd-trace": ("external", "Datadog"),
    "ddtrace": ("external", "Datadog"), "newrelic": ("external", "New Relic"),
}

# NuGet / Maven package prefixes -> (kind, technology).
PACKAGE_SIGNALS = [
    ("AWSSDK.", "external", "AWS"), ("Stripe.net", "external", "Stripe"), ("SendGrid", "external", "SendGrid"),
    ("Twilio", "external", "Twilio"), ("Anthropic", "external", "Anthropic API"), ("OpenAI", "external", "OpenAI API"),
    ("Azure.AI.OpenAI", "external", "Azure OpenAI"),
    ("Microsoft.ApplicationInsights", "external", "Azure Application Insights"),
    ("Sentry", "external", "Sentry"), ("Datadog.Trace", "external", "Datadog"),
    ("NewRelic.Agent", "external", "New Relic"), ("OpenTelemetry.Exporter", "external", "OpenTelemetry collector"),
    ("postgresql", "store", "PostgreSQL"), ("mysql-connector", "store", "MySQL"), ("mssql-jdbc", "store", "SQL Server"),
    ("spring-boot-starter-data-mongodb", "store", "MongoDB"), ("spring-boot-starter-data-redis", "store", "Redis"),
    ("spring-kafka", "store", "Kafka"), ("spring-boot-starter-amqp", "store", "RabbitMQ"),
]

# docker-compose images -> technology of a data store.
COMPOSE_STORES = [
    ("postgres", "PostgreSQL"), ("mysql", "MySQL"), ("mariadb", "MariaDB"), ("mongo", "MongoDB"),
    ("redis", "Redis"), ("elasticsearch", "Elasticsearch"), ("opensearch", "OpenSearch"),
    ("rabbitmq", "RabbitMQ"), ("kafka", "Kafka"), ("mssql", "SQL Server"), ("azure-sql-edge", "SQL Server"),
    ("minio", "MinIO"), ("memcached", "Memcached"), ("qdrant", "Qdrant"), ("chroma", "Chroma"),
]

HTTP_CLIENT = re.compile(r"\bHttpClient\b|\brequests\.|\bhttpx\b|\baiohttp\b|\baxios\b|\bfetch\(|\bRestTemplate\b|\bWebClient\b|\bOkHttp")
URL = re.compile(r"""https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})""")
IGNORED_HOSTS = re.compile(
    r"(^|\.)(localhost|example\.(com|org)|w3\.org|json-schema\.org|schemas\.[a-z.]+|xmlsoap\.org|"
    r"microsoft\.com|aka\.ms|github\.com|githubusercontent\.com|npmjs\.(com|org)|pypi\.org|"
    r"python\.org|mozilla\.org|swagger\.io|openapis\.org|apache\.org|nuget\.org|"
    r"database\.windows\.net|readthedocs\.io)$"
)
PY_IMPORT = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.MULTILINE)
JS_IMPORT = re.compile(r"""(?:from\s+|require\(\s*|import\s*\(\s*|import\s+)['"]([^'"]+)['"]""")


# ---------- helpers ----------

def _rel(repo, path):
    return Path(path).resolve().relative_to(repo).as_posix()


def _line_of(text, index):
    return text.count("\n", 0, index) + 1


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def _source_files(repo, test_dirs):
    files = []
    for file in walk_files(repo, lambda name: name.endswith(SOURCE_EXTENSIONS)):
        rel_parts = file.resolve().relative_to(repo).parts
        if any(part.lower() in TEST_DIRS for part in rel_parts[:-1]):
            continue
        if any(file.resolve().is_relative_to(d) for d in test_dirs):
            continue
        files.append(file.resolve())
    return files


def _strip_json_comments(text):
    return re.sub(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', lambda m: m.group(1) or "", text, flags=re.DOTALL)


def _config_urls(text):
    """(setting name, host) for every URL value in a JSON config, e.g. ("PaymentsUrl", "payments.example")."""
    try:
        data = json.loads(_strip_json_comments(text))
    except ValueError:
        return []

    found = []

    def visit(value, keys):
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, keys + [key])
        elif isinstance(value, list):
            for child in value:
                visit(child, keys)
        elif isinstance(value, str):
            match = URL.match(value.strip())
            if match and not IGNORED_HOSTS.search(match.group(1).lower()):
                # Drop year/number keys and generic leaf names: the setting is what's left.
                named = [k for k in keys if not k.isdigit()]
                generic = {"url", "uri", "baseurl", "apiurl", "endpoint", "host", "address"}
                while len(named) > 1 and named[-1].lower() in generic:
                    named.pop()
                found.append((":".join(named[-1:]) or "config", match.group(1).lower()))

    visit(data, [])
    return found


def registry_get(registry, key, entry):
    return registry.setdefault(key, entry)


def _add(registry, key, entry, evidence):
    item = registry.setdefault(key, entry)
    if evidence and evidence not in item["evidence"] and len(item["evidence"]) < MAX_EVIDENCE:
        item["evidence"].append(evidence)
    return item


# ---------- containers ----------

def _dotnet_containers(repo, projects):
    containers = []
    for project in projects:
        if project["ecosystem"] != ".NET" or project["in_solution"] is False or is_test_project(project["id"]):
            continue
        text = _read(project["path"])
        try:
            root = ET.fromstring(text.encode("utf-8"))
        except ET.ParseError:
            continue
        sdk = root.attrib.get("Sdk", "")
        props = {local_tag(e): (e.text or "").strip() for e in root.iter()}
        packages = [e.attrib.get("Include", "") for e in root.iter() if local_tag(e) == "PackageReference"]
        if "Microsoft.NET.Test.Sdk" in packages:
            continue

        framework = props.get("TargetFramework") or props.get("TargetFrameworks", "").split(";")[0]
        if "AzureFunctionsVersion" in props:
            kind, technology = "function", "Azure Functions"
        elif sdk.endswith(".Web"):
            kind, technology = "web-api", "ASP.NET Core"
        elif sdk.endswith(".BlazorWebAssembly"):
            kind, technology = "web-app", "Blazor WebAssembly"
        elif sdk.endswith(".Worker"):
            kind, technology = "worker", ".NET Worker Service"
        elif props.get("OutputType", "").lower() in ("exe", "winexe"):
            kind, technology = "app", ".NET console app"
        else:
            continue

        containers.append({
            "name": project["id"],
            "kind": kind,
            "technology": f"{technology}, {framework}" if framework else technology,
            "path": _rel(repo, project["path"].parent),
            "root": project["path"],
            "evidence": [f"{project['relative_path']}: Sdk=\"{sdk}\"" if sdk else project["relative_path"]],
        })
    return containers


def _signal_match(names, signals):
    kinds = {}
    for name, kind, technology in signals:
        if name in names and kind not in kinds:
            kinds[kind] = technology
    return kinds


def _python_imports(files):
    names = set()
    for file in files:
        for match in PY_IMPORT.finditer(_read(file)):
            module = match.group(1) or match.group(2)
            parts = module.split(".")
            names.add(parts[0])
            if len(parts) > 1:
                names.add(".".join(parts[:2]))
    return names


def _python_containers(repo):
    distributions = _distributions(repo)
    if not distributions:
        if not any(walk_files(repo, lambda name: re.match(r"requirements.*\.txt$", name))):
            return []
        distributions = [{"name": repo.name, "directory": repo, "file": None, "requirements": []}]

    containers = []
    for dist in distributions:
        directory = dist["directory"]
        requirements = set(dist["requirements"])
        for req_file in directory.glob("requirements*.txt"):
            for line in _read(req_file).splitlines():
                match = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", line)
                if match:
                    requirements.add(normalize(match.group(1)))

        code = [f for f in _python_files(directory) if not any(p in TEST_DIRS for p in f.relative_to(directory).parts[:-1])]
        imports = _python_imports(code)
        names = {normalize(n) for n in requirements} | {normalize(n) for n in imports}
        kinds = _signal_match(names, [(normalize(n), k, t) for n, k, t in PYTHON_CONTAINER_SIGNALS])

        manifest = dist["file"]
        if manifest is not None and manifest.name == "pyproject.toml" and "[project.scripts]" in _read(manifest):
            kinds.setdefault("cli", "CLI")
        if not kinds:
            continue

        evidence = [f"{_rel(repo, manifest) if manifest else _rel(repo, directory)}: {', '.join(kinds.values())}"]
        containers.append({
            "name": dist["name"],
            "kind": " + ".join(kinds),
            "technology": "Python, " + ", ".join(kinds.values()),
            "path": _rel(repo, directory) if directory != repo else ".",
            "root": manifest.resolve() if manifest else None,
            "evidence": evidence,
        })
    return containers


def _node_containers(repo):
    containers = []
    for file in walk_files(repo, lambda name: name == "package.json"):
        try:
            data = json.loads(_read(file))
        except ValueError:
            continue
        if data.get("workspaces"):
            continue
        dependencies = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
        runtime = set(data.get("dependencies") or {})
        kinds = _signal_match(set(dependencies), NODE_CONTAINER_SIGNALS)
        # A server framework only in devDependencies is usually a dev server, not the app.
        kinds = {k: t for k, t in kinds.items() if k == "web-app" or any(n in runtime for n, kk, _ in NODE_CONTAINER_SIGNALS if kk == k)}
        if data.get("bin"):
            kinds.setdefault("cli", "CLI")
        if not kinds and (data.get("scripts") or {}).get("start"):
            kinds["app"] = "Node.js"
        if not kinds:
            continue
        containers.append({
            "name": data.get("name") or file.parent.name,
            "kind": " + ".join(kinds),
            "technology": ", ".join((["Node.js"] if "web-app" not in kinds else []) + [t for t in kinds.values() if t != "Node.js"]),
            "path": _rel(repo, file.parent) if file.parent.resolve() != repo else ".",
            "root": file.resolve(),
            "evidence": [f"{_rel(repo, file)}: {', '.join(kinds.values())}"],
        })
    return containers


def _java_containers(repo, projects):
    containers = []
    for project in projects:
        if not project["ecosystem"].startswith("Java") or is_test_project(project["id"]):
            continue
        path = project["path"]
        text = _read(path) if path.is_file() else ""
        kinds = _signal_match({s for s, _, _ in JAVA_CONTAINER_SIGNALS if s in text}, JAVA_CONTAINER_SIGNALS)
        if "web-api" in kinds:
            kinds.pop("app", None)
        if re.search(r"<packaging>\s*war\s*</packaging>", text):
            kinds.setdefault("web-app", "Java web app (WAR)")
        if re.search(r"\bid\s*\(?\s*['\"]application['\"]|^\s*application\s*$", text, re.MULTILINE):
            kinds.setdefault("app", "Java application")
        if not kinds:
            continue
        containers.append({
            "name": project["id"],
            "kind": " + ".join(kinds),
            "technology": ", ".join(kinds.values()),
            "path": _rel(repo, path.parent if path.is_file() else path),
            "root": path,
            "evidence": [f"{project['relative_path']}: {', '.join(kinds.values())}"],
        })
    return containers


def _compose_services(repo):
    """(service, image, build context, file, line) from docker-compose files, without a YAML parser."""
    services = []
    for file in walk_files(repo, lambda name: re.match(r"(docker-)?compose(\.[\w-]+)?\.ya?ml$", name)):
        lines = _read(file).splitlines()
        in_services, service_indent, current = False, None, None
        for number, line in enumerate(lines, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            if indent == 0:
                in_services = line.startswith("services:")
                current = None
                continue
            if not in_services:
                continue
            if service_indent is None:
                service_indent = indent
            key, _, value = line.strip().partition(":")
            value = value.strip().strip("'\"")
            if indent == service_indent:
                current = {"name": key, "image": None, "build": None, "file": file, "line": number}
                services.append(current)
            elif current and key == "image":
                current["image"] = value
            elif current and key == "build":
                current["build"] = value or "."
            elif current and key == "context" and current["build"] == ".":
                current["build"] = value
    return services


# ---------- main ----------

def _container_scopes(repo, containers, projects, graph):
    """Directories whose files belong to each container: its own folder plus every project it references."""
    path_to_id = {p["path"]: p["id"] for p in projects}
    id_to_dir = {p["id"]: (p["path"].parent if p["path"].is_file() else p["path"]) for p in projects}

    for container in containers:
        scope = {(repo / container["path"]).resolve()}
        root_id = path_to_id.get(container["root"]) if container.get("root") else None
        if root_id in graph:
            seen, stack = set(), [root_id]
            while stack:
                node = stack.pop()
                if node in seen or node not in graph:
                    continue
                seen.add(node)
                stack += graph[node]
            scope |= {id_to_dir[n] for n in seen if n in id_to_dir}
            container["root_component"] = root_id
        container["scope"] = scope


def _components(repo, container, projects, graph, all_containers):
    """Component graph of one container: reachable projects, or the module nodes inside its folder."""
    by_id = {p["id"]: p for p in projects}
    root = container.get("root_component")

    if root:
        nodes, stack = [], [root]
        while stack:
            node = stack.pop()
            if node in nodes or node not in graph:
                continue
            nodes.append(node)
            stack += graph[node]
    else:
        directory = (repo / container["path"]).resolve()
        # Nested containers (a package inside this one's folder) own their own nodes.
        others = [(repo / c["path"]).resolve() for c in all_containers if c is not container]
        nodes = []
        for node, project in by_id.items():
            if node not in graph:
                continue
            path = project["path"]
            if not path.resolve().is_relative_to(directory):
                continue
            if any(o != directory and o.is_relative_to(directory) and path.resolve().is_relative_to(o) for o in others):
                continue
            nodes.append(node)

    nodes = [n for n in nodes if not is_test_project(n)]
    node_set = set(nodes)
    return {
        "nodes": {
            n: {"path": by_id[n]["relative_path"], "group": by_id[n]["group"]}
            for n in sorted(nodes)
        },
        "edges": {n: [t for t in graph[n] if t in node_set] for n in sorted(nodes)},
    }


def _owner_component(file, components, by_id):
    best, best_len = None, -1
    for node in components["nodes"]:
        path = by_id[node]["path"].resolve()
        base = path.parent if path.is_file() and path.suffix not in (".py",) else path
        if node.endswith(" (files)"):
            matches = file.parent == base
        else:
            matches = file == base or file.is_relative_to(base)
        if matches and len(base.parts) > best_len:
            best, best_len = node, len(base.parts)
    return best


def collect_facts(repo_path, graph):
    repo = Path(repo_path).resolve()
    discovery = discover_all(repo)
    projects = [p for p in discovery["projects"] if p["in_solution"] is not False]

    containers = (
        _dotnet_containers(repo, projects)
        + _python_containers(repo)
        + _node_containers(repo)
        + _java_containers(repo, projects)
    )

    stores, externals = {}, {}

    compose_stores = []

    # docker-compose: build services are (or confirm) containers; known images are data stores.
    for service in _compose_services(repo):
        evidence = f"{_rel(repo, service['file'])}:{service['line']}"
        image = (service["image"] or "").lower()
        store = next((tech for key, tech in COMPOSE_STORES if key in image.split(":")[0]), None)
        if store:
            compose_stores.append((store, service))
        elif service["build"]:
            context = (service["file"].parent / service["build"]).resolve()
            match = next((c for c in containers if (repo / c["path"]).resolve() == context), None)
            if match:
                match["evidence"].append(f"{evidence} (compose service {service['name']})")
            elif context.is_relative_to(repo):
                containers.append({
                    "name": service["name"], "kind": "service", "technology": "Docker",
                    "path": _rel(repo, context) if context != repo else ".", "root": None, "evidence": [evidence],
                })
        elif image:
            containers.append({
                "name": service["name"], "kind": "service", "technology": image,
                "path": None, "root": None, "evidence": [evidence],
            })

    # Nothing runnable found: treat the whole repository as one container, so
    # the component level still has a home.
    if not containers and graph:
        containers.append({
            "name": repo.name, "kind": "unknown", "technology": "", "path": ".", "root": None,
            "evidence": ["no entry point detected; whole repository"],
        })

    used_ids = set()
    for container in containers:
        base = slug(container["name"])
        container["id"] = base if base not in used_ids else f"{base}-{len(used_ids)}"
        used_ids.add(container["id"])

    runnable = [c for c in containers if c["path"] is not None]
    _container_scopes(repo, runnable, projects, graph)
    for container in runnable:
        container["components"] = _components(repo, container, projects, graph, runnable)

    test_dirs = [
        (p["path"].parent if p["path"].is_file() else p["path"]).resolve()
        for p in projects if is_test_project(p["id"])
    ]
    by_id = {p["id"]: p for p in projects}

    def owners(file):
        result = []
        for container in runnable:
            if any(file.is_relative_to(d) for d in container["scope"]):
                result.append((container["id"], _owner_component(file, container["components"], by_id)))
        return result

    def record(registry, key, entry, file, line):
        found = owners(file)
        item = registry.setdefault(key, entry)
        evidence = f"{_rel(repo, file)}:{line}"
        # One line per file is enough evidence.
        if not any(e.split(":")[0] == evidence.split(":")[0] for e in item["evidence"]):
            # Evidence from code a container owns comes first.
            owned = item.setdefault("owned", [])
            if found:
                item["evidence"].insert(len([e for e in item["evidence"] if e in owned]), evidence)
                owned.append(evidence)
            else:
                item["evidence"].append(evidence)
            del item["evidence"][MAX_EVIDENCE:]
        for container_id, component in found:
            item["used_by"].add(container_id)
            if component:
                item["used_by_components"].setdefault(container_id, set()).add(component)

    def new_entry(technology):
        return {"technology": technology, "evidence": [], "used_by": set(), "used_by_components": {}}

    for technology, service in compose_stores:
        record(stores, technology, new_entry(technology), service["file"].resolve(), service["line"])

    for file in _source_files(repo, test_dirs):
        text = _read(file)

        for pattern, kind, technology in CODE_SIGNALS:
            match = re.search(pattern, text)
            if match:
                record(stores if kind == "store" else externals, technology, new_entry(technology), file, _line_of(text, match.start()))

        if file.suffix == ".py":
            imports = [(m.group(1) or m.group(2), m.start()) for m in PY_IMPORT.finditer(text)]
        elif file.suffix in (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"):
            imports = [(m.group(1), m.start()) for m in JS_IMPORT.finditer(text)]
        else:
            imports = []
        for module, index in imports:
            parts = module.split("/") if "/" in module else module.split(".")
            candidates = [module, parts[0], "/".join(parts[:2]) if module.startswith("@") else ".".join(parts[:2])]
            hit = next((IMPORT_SIGNALS[c] for c in candidates if c in IMPORT_SIGNALS), None)
            if hit:
                kind, technology = hit
                record(stores if kind == "store" else externals, technology, new_entry(technology), file, _line_of(text, index))

        if HTTP_CLIENT.search(text):
            for match in URL.finditer(text):
                host = match.group(1).lower()
                if not IGNORED_HOSTS.search(host):
                    record(externals, host, new_entry(host), file, _line_of(text, match.start()))

    # Package references (NuGet, Maven) that imply a store or a third-party API.
    for project in projects:
        if is_test_project(project["id"]) or not project["path"].is_file():
            continue
        text = _read(project["path"])
        for prefix, kind, technology in PACKAGE_SIGNALS:
            match = re.search(r"""(Include="|<artifactId>|['":])""" + re.escape(prefix), text)
            if match:
                record(stores if kind == "store" else externals, technology, new_entry(technology), project["path"], _line_of(text, match.start()))

    # URLs in appsettings*.json: one external system per setting, so a per-state or
    # per-region map of URLs ("PaymentsUrl": {"eu": ..., "us": ...}) is one box.
    for file in walk_files(repo, lambda name: re.match(r"appsettings.*\.json$", name)):
        text = _read(file)
        for setting, host in _config_urls(text):
            index = text.find(host)
            entry = new_entry(setting)
            item = registry_get(externals, setting, entry)
            item.setdefault("hosts", set()).add(host)
            record(externals, setting, entry, file.resolve(), _line_of(text, max(index, 0)))

    def finish(registry, prefix):
        items = []
        for key, item in sorted(registry.items()):
            items.append({
                "id": f"{prefix}-{slug(key)}",
                "name": key,
                "technology": ", ".join(sorted(item["hosts"])[:3]) + (" …" if len(item["hosts"]) > 3 else "") if item.get("hosts") else item["technology"],
                "evidence": item["evidence"],
                "used_by": sorted(item["used_by"]),
                "used_by_components": {c: sorted(v) for c, v in sorted(item["used_by_components"].items())},
            })
        return items

    return {
        "repository": repo.name,
        "containers": [
            {
                key: container.get(key)
                for key in ("id", "name", "kind", "technology", "path", "evidence", "components")
            }
            for container in containers
        ],
        "data_stores": finish(stores, "db"),
        "external_systems": finish(externals, "ext"),
    }



if __name__ == "__main__":
    try:
        from scripts.build_graph import build_dependency_graph
    except ImportError:
        from build_graph import build_dependency_graph

    repo_arg = sys.argv[1]
    print(json.dumps(collect_facts(repo_arg, build_dependency_graph(repo_arg)), indent=2, default=str))
