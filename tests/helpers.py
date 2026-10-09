import copy
import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "c4-diagrams"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))


ABS_PATH_PLACEHOLDER = "<abs-path>"
MASK_PLACEHOLDER = "<masked>"

_MASK_BY_NAME = {"run_id", "Generated On"}
_MASK_BY_SUBSTRING = ("timestamp",)


def write(root, files, crlf=False):
    """Write {relative path: text} under root and return the paths in order."""
    paths = []
    for relative, text in files.items():
        path = Path(root) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
        paths.append(path)
    return paths


def line_of(text, needle):
    """1-based number of the first line containing needle."""
    return next(number for number, line in enumerate(text.splitlines(), 1) if needle in line)


def _should_mask_key(key):
    if key in _MASK_BY_NAME:
        return True
    return any(sub in key for sub in _MASK_BY_SUBSTRING)


def _mask_value(value):
    """Recursively mask volatile fields inside a parsed JSON-like structure."""
    if isinstance(value, dict):
        return {
            key: (
                MASK_PLACEHOLDER if _should_mask_key(key)
                else _mask_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_mask_value(item) for item in value]
    if isinstance(value, str) and value.startswith("/"):
        return ABS_PATH_PLACEHOLDER
    return value


def mask_volatile(obj):
    """Return a deep-copied JSON structure with volatile fields replaced.

    Recurses into dicts and lists. By-name, replaces keys named ``run_id`` or
    ``Generated On`` and any key containing ``timestamp``. By-value, replaces
    any string that looks like an absolute filesystem path. The intent is to
    keep golden-file comparisons stable: the only field that actually varies
    today is ``summary["output_folder"]`` (absolute path), but the name-based
    masks are included so the helper stays correct for free when SPEC-09
    (``run_id``) lands and whenever timestamp keys appear.
    """
    return _mask_value(copy.deepcopy(obj))


def run_analyzer(fixture, tmp, *, no_svg=True):
    """Run the analyzer in ``fixture``; write outputs under ``tmp``.

    Uses the public ``RepositoryAnalyzer.run()`` entry point. ``no_svg`` is on
    by default so AC1 (no Node.js / no network) holds without mocking.

    Returns the ``(facts, summary)`` pair as parsed JSON dicts, read off disk
    so the values are byte-identical to what the CLI wrote.
    """
    from scripts.analyze_repository import RepositoryAnalyzer

    analyzer = RepositoryAnalyzer(str(fixture), str(tmp), no_svg=no_svg)
    analyzer.run()

    output = Path(tmp)
    facts = json.loads((output / "c4-facts.json").read_text(encoding="utf-8"))
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    return facts, summary
