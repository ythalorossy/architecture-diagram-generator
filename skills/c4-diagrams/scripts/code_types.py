"""
Types (classes, interfaces, enums, records, structs) and their public methods,
read from source with regexes, for the C4 Level 4 (code) diagrams. No compiler
or toolchain is needed; like the rest of the skill it is a best-effort reading
of the code.

    extract(files) -> {type name: {name, kind, language, file, line, bases,
                       interfaces, methods, values, depends_on, embeds}}
"""
from pathlib import Path
import re

LANGUAGES = {
    ".cs": "cs", ".java": "java", ".kt": "kotlin", ".go": "go", ".py": "python",
    ".ts": "ts", ".tsx": "ts", ".js": "ts", ".jsx": "ts", ".mjs": "ts",
}
GENERATED = re.compile(
    r"(\.designer\.cs|\.g\.cs|\.g\.i\.cs|^reference\.cs|_pb2\.py|\.generated\.\w+|\.d\.ts|\.min\.m?js)$",
    re.IGNORECASE,
)
QUOTES = {"cs": "\"'", "java": "\"'", "kotlin": "\"'", "go": "\"'`", "python": "\"'", "ts": "\"'`"}
TRIPLE = {"cs": ('"""',), "java": ('"""',), "kotlin": ('"""',), "python": ('"""', "'''")}
# Words a member regex can mistake for a return type.
NOT_TYPES = {
    "return", "new", "await", "throw", "else", "delegate", "event", "operator", "implicit", "explicit",
    "using", "yield", "public", "private", "protected", "internal", "static", "var", "case", "goto",
}
NO_BODY = re.compile(r";|\b(?:class|interface|object|enum|record|struct|fun|func|def|type)\b")


def is_generated(name):
    return GENERATED.search(name) is not None


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
    except OSError:
        return ""


def _line_of(text, index):
    return text.count("\n", 0, index) + 1


def _mask(text, language):
    """The text with comments and string contents blanked (newlines kept), so offsets still match."""
    out = list(text)
    n = len(text)
    comment = "#" if language == "python" else "//"

    def blank(start, end):
        for k in range(start, min(end, n)):
            if out[k] != "\n":
                out[k] = " "

    i = 0
    while i < n:
        triple = next((q for q in TRIPLE.get(language, ()) if text.startswith(q, i)), None)
        if text.startswith(comment, i):
            end = text.find("\n", i)
            end = n if end < 0 else end
            blank(i, end)
            i = end
        elif language != "python" and text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            blank(i, end)
            i = end
        elif triple:
            end = text.find(triple, i + 3)
            end = n if end < 0 else end + 3
            blank(i + 3, end - 3)
            i = end
        elif text[i] in QUOTES[language]:
            quote = text[i]
            raw = (language == "go" and quote == "`") or (language == "cs" and text[i - 1:i] == "@")
            j = i + 1
            while j < n:
                c = text[j]
                if c == "\\" and not raw:
                    j += 2
                    continue
                if c == quote:
                    if raw and language == "cs" and text[j + 1:j + 2] == quote:
                        j += 2
                        continue
                    break
                if c == "\n" and quote != "`" and not raw:
                    break
                j += 1
            blank(i + 1, j)
            i = j + 1
        else:
            i += 1
    return "".join(out)


def _block_end(masked, start):
    """Index of the brace that closes the one at start, or len(masked) when it never closes."""
    depth = 0
    for k in range(start, len(masked)):
        if masked[k] == "{":
            depth += 1
        elif masked[k] == "}":
            depth -= 1
            if depth == 0:
                return k
    return len(masked)


def _body(masked, header_end):
    """(open brace, close brace) of the body after a type header, or None when it has none."""
    brace = masked.find("{", header_end)
    if brace < 0 or NO_BODY.search(masked, header_end, brace):
        return None
    return brace, _block_end(masked, brace)


def _flatten(text):
    """Depth-0 text of a body: nested blocks blanked, so member regexes never see method bodies."""
    out, depth = [], 0
    for c in text:
        if c == "{":
            out.append(c if depth == 0 else " ")
            depth += 1
        elif c == "}":
            depth = max(depth - 1, 0)
            out.append(c if depth == 0 else " ")
        else:
            out.append(c if depth == 0 or c == "\n" else " ")
    return "".join(out)


def _split_top(text, sep=","):
    """Split on sep outside brackets: "A<B, C>, D" -> ["A<B, C>", "D"]."""
    parts, depth, current = [], 0, []
    for c in text:
        if c in "<([{":
            depth += 1
        elif c in ">)]}":
            depth = max(depth - 1, 0)
        if c == sep and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(c)
    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def _type_name(text):
    """Bare type name: "pkg.Base<T>" -> "Base", "Base()" -> "Base", "*pkg.T" -> "T"."""
    text = re.sub(r"\s+by\s+.*", "", text.strip(), flags=re.S)
    text = re.sub(r"[<\[(].*", "", text, flags=re.S).strip()
    return text.split(".")[-1].strip("?*&! ")


def _refs(text):
    """Capitalized identifiers in a type expression: candidate references to other types."""
    return set(re.findall(r"\b[A-Z]\w*", text or ""))


def _param_names(params, language):
    names = []
    for part in _split_top(params):
        part = re.sub(r"=.*", "", part, flags=re.S)
        part = re.sub(r"@\w+(?:\([^)]*\))?", " ", part)
        if language in ("kotlin", "ts", "python"):
            words = re.findall(r"\w+", part.split(":", 1)[0])
        elif language == "go":
            words = re.findall(r"\w+", part)[:1]
        else:
            words = re.findall(r"\w+", re.sub(r"\[[^\]]*\]", " ", part))
        if words and words[-1] not in ("self", "cls"):
            names.append(words[-1])
    return names


def _param_refs(params, language):
    refs = set()
    for part in _split_top(params):
        part = re.sub(r"=.*", "", part, flags=re.S)
        if language in ("kotlin", "ts", "python"):
            part = part.split(":", 1)[1] if ":" in part else ""
        refs |= _refs(part)
    return refs


def _method(name, params, ret, language):
    ret = " ".join((ret or "").split())
    return f"{name}({', '.join(_param_names(params, language))})" + (f" {ret}" if ret else "")


def _new_type(name, kind, language, file, line):
    return {
        "name": name, "kind": kind, "language": language, "file": Path(file), "line": line,
        "bases": [], "interfaces": [], "methods": [], "values": [], "depends_on": [], "embeds": [],
        "_refs": set(),
    }


def _enum_values(flat):
    values = []
    for part in _split_top(flat.split(";", 1)[0]):
        m = re.match(r"(?:\[[^\]]*\]\s*|@\w+(?:\([^)]*\))?\s*)*([A-Za-z_]\w*)", part)
        if m:
            values.append(m.group(1))
    return values


def _top_level(found):
    """[(name index, body span, type)] -> the types not declared inside another type's body."""
    spans = [span for _, span, _ in found if span]
    return [t for start, _, t in found if not any(s < start < e for s, e in spans)]


# ---------- C# ----------

CS_TYPE = re.compile(
    r"^[ \t]*(?:\[[^\]\n]*\][ \t]*)*"
    r"(?P<mods>(?:(?:public|internal|private|protected|abstract|sealed|static|partial|readonly|ref|unsafe|new|file)\s+)*)"
    r"(?P<kw>class|interface|record\s+struct|record\s+class|record|struct|enum)\s+(?P<name>\w+)"
    r"(?:\s*<[^>{;]*>)?(?:\s*\((?P<params>[^)]*)\))?"
    r"(?:\s*:\s*(?P<bases>[^{;]*?))?\s*(?:\bwhere\b[^{;]*)?(?=[{;])",
    re.MULTILINE,
)
CS_METHOD = re.compile(
    r"^[ \t]*(?:\[[^\]\n]*\][ \t]*)*"
    r"(?P<mods>(?:(?:public|private|protected|internal|static|async|virtual|override|abstract|new|sealed|extern|unsafe|partial|readonly)\s+)*)"
    r"(?P<ret>\w[\w.]*(?:\s*<[^()]*?>)?(?:\[\])*\??)\s+(?P<name>\w+)\s*(?:<[^>()]*>)?\s*\((?P<params>[^)]*)\)",
    re.MULTILINE,
)
CS_FIELD = re.compile(
    r"^[ \t]*(?:(?:private|protected|internal|public|readonly|static|const|required|volatile)\s+)+"
    r"(?P<type>\w[\w.]*(?:\s*<[^()=;]*?>)?(?:\[\])*\??)\s+\w+\s*(?:[;={]|=>)",
    re.MULTILINE,
)


def _constructor_refs(name, flat, language):
    refs = set()
    for c in re.finditer(r"\b" + re.escape(name) + r"\s*\((?P<params>[^)]*)\)", flat):
        refs |= _param_refs(c["params"], language)
    return refs


def _parse_cs(text, file):
    masked = _mask(text, "cs")
    found = []
    for m in CS_TYPE.finditer(masked):
        keyword = m["kw"].split()[0]
        kind = {"interface": "interface", "enum": "enum", "record": "record", "struct": "struct"}.get(keyword, "class")
        if kind == "class" and "abstract" in m["mods"].split():
            kind = "abstract"
        t = _new_type(m["name"], kind, "cs", file, _line_of(masked, m.start("name")))
        span = _body(masked, m.end())
        flat = _flatten(masked[span[0] + 1:span[1]]) if span else ""
        if kind == "enum":
            t["values"] = _enum_values(flat)
            found.append((m.start("name"), span, t))
            continue
        for base in (_type_name(b) for b in _split_top(m["bases"] or "")):
            if kind == "interface":
                t["bases"].append(base)
            elif not t["bases"] and not re.match(r"I[A-Z]", base):
                t["bases"].append(base)
            else:
                t["interfaces"].append(base)
        for method in CS_METHOD.finditer(flat):
            mods = method["mods"].split()
            if method["ret"] in NOT_TYPES:
                continue
            if (kind != "interface" and "public" not in mods) or "private" in mods:
                continue
            t["methods"].append(_method(method["name"], method["params"], method["ret"], "cs"))
        for field in CS_FIELD.finditer(flat):
            t["_refs"] |= _refs(field["type"])
        t["_refs"] |= _constructor_refs(m["name"], flat, "cs")
        if m["params"]:
            t["_refs"] |= _param_refs(m["params"], "cs")
        found.append((m.start("name"), span, t))
    return _top_level(found), []


PARSERS = {"cs": _parse_cs}


def _merge(types, new):
    """Add a type; a second declaration of the same name (partial class, another namespace) is merged."""
    old = types.get(new["name"])
    if old is None:
        types[new["name"]] = new
        return
    for key in ("bases", "interfaces", "methods", "values", "embeds"):
        old[key] += [v for v in new[key] if v not in old[key]]
    old["_refs"] |= new["_refs"]


def extract(files):
    """{type name: type} for the given source files (generated files and unknown languages are skipped)."""
    types, receiver_methods = {}, []
    for file in files:
        file = Path(file)
        parser = PARSERS.get(LANGUAGES.get(file.suffix.lower()))
        if parser is None or is_generated(file.name):
            continue
        found, methods = parser(_read(file), file)
        receiver_methods += methods
        for t in found:
            _merge(types, t)
    for receiver, method in receiver_methods:  # Go: methods can live in another file of the package
        if receiver in types and method not in types[receiver]["methods"]:
            types[receiver]["methods"].append(method)
    names = set(types)
    for t in types.values():
        related = set(t["bases"]) | set(t["interfaces"]) | set(t["embeds"]) | {t["name"]}
        t["depends_on"] = sorted((t.pop("_refs") & names) - related)
    return dict(sorted(types.items()))
