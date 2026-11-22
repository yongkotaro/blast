"""Collect source line coverage keyed by stable pytest node IDs during image build."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(os.environ["SQLGLOT_ROOT"]).resolve()
OUT = Path(os.environ["COVERAGE_MAP"])
result = {}
current = None


def trace(frame, event, arg):
    if event != "line" or current is None:
        return trace
    name = frame.f_code.co_filename
    if name.startswith(str(ROOT) + os.sep):
        rel = name[len(str(ROOT)) + 1:]
        if rel.startswith("sqlglot/") or rel.startswith("tests/"):
            result[current].add((rel, frame.f_lineno))
    return trace


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    global current
    current = item.nodeid
    result[current] = set()
    sys.settrace(trace)
    try:
        yield
    finally:
        sys.settrace(None)
        current = None


def pytest_sessionfinish(session, exitstatus):
    OUT.write_text(json.dumps({k: sorted(v) for k, v in result.items()}, separators=(",", ":")))
