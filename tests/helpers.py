import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "c4-diagrams"
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))


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
