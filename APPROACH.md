# Selector approach

The image checks out sqlglot at `eb11aec4be8cb2122afe713a4816662c3f0fb2fa`, installs `requirements.lock`, sets `PYTHONPATH` and `SKIP_INTEGRATION=0`, and traces the full pytest suite during the Docker build. The resulting map stores source lines by pytest node ID, plus AST scope ranges and imports. Build time is outside the scored runtime. The map is installed readable by `nobody`; sample answers are excluded from the build context.

At runtime, `selector.py` parses each independent unified diff. It queries baseline coverage using old line numbers, includes the smallest enclosing AST scope for changed or inserted Python code, includes directly importing test files when module level code is touched or coverage is absent, and includes the corresponding dialect test file for dialect, parser, or generator changes. Fixture edits select the same named test; unknown files select all tests. This conservative fallback can increase cost, and tracing cannot prove that new behavior is harmless or capture every dynamic dependency.

The selector evaluates one to eight occupied workers using longest processing time first and integer milliseconds, including 2,000 milliseconds per worker. It emits one JSON line per commit.

## Commands

- `make sample`: build and score a sample run.
- `make check`: validate answer format.
- `python3 -m unittest -q test_selector.py`: focused local parser and assignment tests.

## Local measurements and limits

The untouched starter's existing `output.jsonl` scored **1210.470 simulated seconds, zero misses**. Docker build and runtime verification were unavailable in this workspace because access to `/var/run/docker.sock` returned `Operation not permitted`; GitHub also could not be resolved for a local checkout. Thus there is no measured final sample score, final miss count, or container CPU usage here. The Makefile mirrors the runtime flags but does not enforce a deadline. For an independent run, apply an external three-minute timeout and inspect the container's process CPU usage under the scorer limits. The generated map and full pytest build must be checked against the ten-minute build deadline in a Docker-enabled environment.
