"""Source coverage guided test selection for independent sqlglot patches."""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path('/data')
MAP = Path('/app/maps.json')
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


def parse_patch(text):
    """Yield (old path, new path, old touched lines, insertion anchors)."""
    old = new = None
    touched, anchors = set(), set()
    old_line = new_line = None
    def finish():
        if old is not None or new is not None:
            return old, new, touched, anchors
    for line in text.splitlines():
        if line.startswith('diff --git '):
            record = finish()
            if record:
                yield record
            parts = line.split(' ', 3)
            old = parts[2][2:] if len(parts) > 3 and parts[2].startswith('a/') else None
            new = parts[3][2:] if len(parts) > 3 and parts[3].startswith('b/') else None
            touched, anchors = set(), set()
            old_line = new_line = None
        elif line.startswith('rename from '):
            old = line[len('rename from '):]
        elif line.startswith('rename to '):
            new = line[len('rename to '):]
        elif line.startswith('--- '):
            p = line[4:]
            old = p[2:] if p.startswith('a/') else None
        elif line.startswith('+++ '):
            p = line[4:]
            new = p[2:] if p.startswith('b/') else None
        elif line.startswith('@@ '):
            m = HUNK.match(line)
            if m:
                old_line, new_line = int(m[1]), int(m[3])
        elif old_line is not None and line:
            tag = line[0]
            if tag == '-':
                touched.add(old_line)
                old_line += 1
            elif tag == '+':
                anchors.update((max(1, old_line - 1), old_line))
                new_line += 1
            elif tag == ' ':
                old_line += 1
                new_line += 1
    record = finish()
    if record:
        yield record


def choose_workers(numbers, durations):
    """LPT for each worker count, scored in the scorer's integer milliseconds."""
    if not numbers:
        return []
    ordered = sorted(numbers, key=lambda n: (-durations[n], n))
    best = None
    for count in range(1, min(8, len(ordered)) + 1):
        workers = [[] for _ in range(count)]
        loads = [0] * count
        for n in ordered:
            i = min(range(count), key=lambda j: (loads[j], j))
            workers[i].append(n)
            loads[i] += durations[n]
        cost = max(loads) + 2000 * count
        if best is None or cost < best[0]:
            best = cost, workers
    return best[1]


def select(records, maps, by_id, by_file):
    picked = set()
    line_map = maps['lines']
    file_map = maps['files']
    funcs = maps['functions']
    for old, new, touched, anchors in records:
        path = old or new
        if not path:
            continue
        ids = set()
        if path.startswith('tests/fixtures/'):
            stem = Path(path).stem
            ids.update(tid for tid in by_id if tid.split('::')[-1] == 'test_' + stem)
            # Fixture names are sometimes plural while their test method is
            # singular (pushdown_projections -> test_pushdown_projection).
            variants = {stem, stem.removesuffix('s')}
            ids.update(tid for tid in by_id if tid.startswith('tests/test_optimizer.py::')
                       and tid.split('::')[-1] in {'test_' + v for v in variants})
            if not ids:
                ids.update(by_file.get('tests/test_optimizer.py', ()))
        elif path.startswith('tests/'):
            ids.update(by_file.get(path, ()))
            ids.update(file_map.get(path, ()))
            if path.endswith('conftest.py'):
                prefix = str(Path(path).parent) + '/'
                ids.update(tid for tid in by_id if tid.startswith(prefix))
        elif path.startswith('sqlglot/') and path.endswith('.py'):
            # Query baseline old lines. An insertion uses adjacent old lines and
            # all tests covering its enclosing AST scope.
            for line in touched | anchors:
                ids.update(line_map.get(f'{path}:{line}', ()))
                for start, end in funcs.get(path, ()):
                    if start <= line <= end:
                        # Narrowest enclosing scope avoids a broad class match.
                        narrower = [(a, b) for a, b in funcs[path] if a <= line <= b]
                        a, b = min(narrower, key=lambda x: x[1] - x[0])
                        for n in range(a, b + 1):
                            ids.update(line_map.get(f'{path}:{n}', ()))
                        break
            # Changed import-time declarations and uncovered code need module
            # coverage; tests in the corresponding dialect are a useful guard.
            if not ids or not (touched or anchors) or any(line <= 15 for line in touched | anchors):
                ids.update(file_map.get(path, ()))
                module = path[:-3].replace('/', '.')
                for source, deps in maps['imports'].items():
                    if source.startswith('tests/') and any(d == module or d.startswith(module + '.') for d in deps):
                        ids.update(by_file.get(source, ()))
            # Tracing starts after collection: imports and class attributes
            # are outside per-test coverage. These suites exercise the shared
            # optimizer and dialect paths, including branches newly enabled
            # by the patch that baseline line coverage cannot observe.
            if path.startswith(('sqlglot/optimizer/', 'sqlglot/parsers/',
                                'sqlglot/dialects/')) or path in ('sqlglot/serde.py', 'sqlglot/transforms.py'):
                ids.update(by_file.get('tests/test_optimizer.py', ()))
            if path.startswith('sqlglot/optimizer/') or path == 'sqlglot/serde.py':
                ids.update(by_file.get('tests/test_executor.py', ()))
            base = Path(path).stem
            if path.startswith(('sqlglot/dialects/', 'sqlglot/parsers/', 'sqlglot/generators/')):
                dialect = 'tests/dialects/test_' + base + '.py'
                ids.update(by_file.get(dialect, ()))
        else:
            # Unknown configuration or data can affect collection or any test.
            ids.update(by_id)
        picked.update(by_id[tid] for tid in ids if tid in by_id)
    return picked


def main():
    data = json.loads((DATA / 'tests.json').read_text())['tests']
    by_id = {t['id']: t['number'] for t in data}
    by_file = defaultdict(set)
    for t in data:
        by_file[t['file']].add(t['id'])
    durations = {t['number']: round(t['seconds'] * 1000) for t in data}
    maps = json.loads(MAP.read_text())
    for patch in sorted((DATA / 'commits').glob('*.patch')):
        nums = select(parse_patch(patch.read_text()), maps, by_id, by_file)
        print(json.dumps({'commit': patch.stem, 'workers': choose_workers(nums, durations)}, separators=(',', ':')))
    print(f'processed {len(list((DATA / "commits").glob("*.patch")))} commits', file=sys.stderr)


if __name__ == '__main__':
    main()
