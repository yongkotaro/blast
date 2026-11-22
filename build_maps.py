"""Produce maps from the pinned sqlglot source and a full pytest trace."""
import ast
import json
import os
from collections import defaultdict
from pathlib import Path

root = Path(os.environ['SQLGLOT_ROOT'])
raw = json.loads(Path(os.environ['COVERAGE_MAP']).read_text())
lines = defaultdict(set)
files = defaultdict(set)
for tid, hits in raw.items():
    for path, line in hits:
        lines[f'{path}:{line}'].add(tid)
        files[path].add(tid)

# AST information supplies enclosing functions for insertions and changed lines
# that the baseline execution never reached.
functions = {}
imports = {}
for path in list(root.glob('sqlglot/**/*.py')) + list(root.glob('tests/**/*.py')):
    rel = path.relative_to(root).as_posix()
    try:
        tree = ast.parse(path.read_text())
    except (SyntaxError, UnicodeError):
        continue
    spans = []
    deps = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            spans.append([node.lineno, node.end_lineno or node.lineno])
        elif isinstance(node, ast.Import):
            deps.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            deps.add(node.module)
    functions[rel] = spans
    imports[rel] = sorted(deps)

out = {'lines': {k: sorted(v) for k, v in lines.items()},
       'files': {k: sorted(v) for k, v in files.items()},
       'functions': functions, 'imports': imports}
Path('/app/maps.json').write_text(json.dumps(out, separators=(',', ':')))
