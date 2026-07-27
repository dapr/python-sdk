# AGENTS.md — Dapr Python SDK

This file provides context for AI agents working on the Dapr Python SDK.
The project is the official Python SDK for [Dapr](https://dapr.io/) (Distributed Application Runtime),
enabling Python developers to build distributed applications using Dapr building blocks.

Repository: https://github.com/dapr/python-sdk
License: Apache 2.0

> **Deeper documentation lives alongside the code.** This root file gives you the big picture and
> tells you where to look. Each extension and the examples directory has its own `AGENTS.md` with
> detailed architecture, APIs, and patterns.

## Project structure

```
dapr/                        # Core SDK package (single PyPI dist: `pip install dapr`)
├── actor/                   # Actor framework (virtual actor model)
├── aio/                     # Async I/O modules
├── clients/                 # Dapr clients (gRPC and HTTP)
├── common/                  # Shared utilities
├── conf/                    # Configuration (settings, environment)
├── proto/                   # Auto-generated gRPC protobuf stubs (DO NOT EDIT)
├── serializers/             # JSON and pluggable serializers
├── version/                 # Version metadata
└── ext/                     # Extensions, installable as extras to the base package
    ├── fastapi/             #   FastAPI integration         ← see dapr/ext/fastapi/AGENTS.md   (`pip install dapr[fastapi]`)
    ├── flask/               #   Flask integration           ← see dapr/ext/flask/AGENTS.md     (`pip install dapr[flask]`)
    ├── grpc/                #   gRPC App extension          ← see dapr/ext/grpc/AGENTS.md      (`pip install dapr[grpc]`)
    ├── langgraph/           #   LangGraph checkpointer      ← see dapr/ext/langgraph/AGENTS.md (`pip install dapr[langgraph]`)
    ├── strands/             #   Strands agent sessions      ← see dapr/ext/strands/AGENTS.md   (`pip install dapr[strands]`)
    └── workflow/            #   Workflow authoring          ← see dapr/ext/workflow/AGENTS.md  (`pip install dapr[workflow]`)

flask_dapr/                  # Deprecation shim: re-exports dapr.ext.flask with FutureWarning

tests/                       # Unit tests (mirrors dapr/ package structure)
├── ext/                     #   Extension tests, one subdir per extension
├── examples/                #   Output-based tests that run examples and check stdout
├── integration/             #   Programmatic SDK tests using DaprClient directly
examples/                    # User-facing example applications  ← see examples/AGENTS.md
docs/                        # Sphinx documentation source
tools/                       # Build and release scripts
```

## Key architectural patterns

- **Namespace packages**: `dapr.ext` is an implicit PEP 420 namespace package. See the Gotchas section below before adding anything at that path.
- **Client architecture**: `DaprGrpcClient` (primary, high-performance) and HTTP-based clients. Both implement shared interfaces.
- **Actor model**: `Actor` base class, `ActorInterface` with `@actormethod` decorator, `ActorProxy`/`ActorProxyFactory` for client-side references, `ActorRuntime` for server-side hosting.
- **Serialization**: Pluggable via `Serializer` base class. `DefaultJSONSerializer` is the default.
- **Proto files**: Auto-generated from Dapr proto definitions. Never edit files under `dapr/proto/` directly.

## Extension overview

Extensions are bundled into the core `dapr` wheel and exposed as installable extras. Each one lives under `dapr/ext/<name>/` with its own `AGENTS.md`.

| Extra | Import path | Purpose | Active development |
|-------|-------------|---------|--------------------|
| `dapr[workflow]` | `dapr.ext.workflow` | Durable workflow orchestration (durabletask vendored internally) | **High**, major focus area |
| `dapr[grpc]` | `dapr.ext.grpc` | gRPC server for Dapr callbacks (methods, pub/sub, bindings, jobs) | Moderate |
| `dapr[fastapi]` | `dapr.ext.fastapi` | FastAPI integration for pub/sub and actors | Moderate |
| `dapr[flask]` | `dapr.ext.flask` | Flask integration for pub/sub and actors (legacy `flask_dapr` import path is a deprecated shim) | Low |
| `dapr[langgraph]` | `dapr.ext.langgraph` | LangGraph checkpoint persistence to Dapr state store | Moderate |
| `dapr[strands]` | `dapr.ext.strands` | Strands agent session management via Dapr state store | New |

The previously-separate distributions (`dapr-ext-*`, `flask-dapr`) are no longer published. `dapr/__init__.py` emits a `FutureWarning` if it detects a legacy install at import time; see `RELEASE.md` for the migration recipe.

## Examples and testing

The `examples/` directory contains user-facing example applications. These are validated by two test suites:

- **`tests/examples/`** — Output-based tests that run examples via `dapr run` and check stdout for expected strings. Uses a `DaprRunner` helper to manage process lifecycle. See `examples/AGENTS.md`.
- **`tests/integration/`** — Programmatic SDK tests that call `DaprClient` methods directly and assert on return values, gRPC status codes, and SDK types. More reliable than output-based tests since they don't depend on print statement formatting. See `tests/integration/AGENTS.md`.

Quick reference:
```bash
uv run pytest tests/examples/                          # Run output-based example tests
uv run pytest tests/examples/test_state_store.py       # Run a single example test
uv run pytest tests/integration/                       # Run programmatic SDK tests
uv run pytest tests/integration/test_invoke.py         # Run a single integration test
```

## Python version support

- **Minimum**: Python 3.10
- **Tested**: 3.10, 3.11, 3.12, 3.13, 3.14
- **Target version for tooling**: `py310` (ruff, mypy)

## Development setup

Install all packages in editable mode with dev dependencies:

```bash
uv sync --all-packages --group dev
```

## Running tests

Tests use Python's built-in `unittest` framework with `coverage`. The vendored durabletask tests use `pytest`.

```bash
# All unit tests. pytest is required: `unittest discover` silently skips the
# pytest-style tests under tests/ext/flask and tests/ext/workflow/durabletask.
uv run pytest -m "not e2e" ./tests --ignore=tests/integration --ignore=tests/examples

# Single extension (unittest discover works for these — no pytest-style tests):
uv run python -m unittest discover -v ./tests/ext/workflow
uv run python -m unittest discover -v ./tests/ext/grpc
uv run python -m unittest discover -v ./tests/ext/fastapi
uv run python -m unittest discover -v ./tests/ext/langgraph
uv run python -m unittest discover -v ./tests/ext/strands

# pytest-style suites:
uv run pytest -m "not e2e" ./tests/ext/workflow/durabletask/
uv run pytest ./tests/ext/flask/test_shim_deprecation.py

# Run linting and formatting
uv run ruff check --fix && uv run ruff format

# Run type checking
uv run mypy

# Run output-based example tests (requires Dapr runtime)
uv run pytest tests/examples/

# Run programmatic integration tests (requires Dapr runtime)
uv run pytest tests/integration/
```

## Code style and linting

**Formatter/Linter**: Ruff (v0.14.1)

Key rules:
- **Line length**: 100 characters (E501 is currently ignored, but respect the 100-char target)
- **Quote style**: Single quotes
- **Import sorting**: isort-compatible (ruff `I` rules)
- **Target**: Python 3.10
- **Excluded from linting**: `.github/`, `dapr/proto/`

Run formatting and lint fixes:

```bash
uv run ruff check --fix && uv run ruff format
```

**Type checking**: MyPy

```bash
uv run mypy
```

MyPy checks the `dapr` and `flask_dapr` packages (covering all bundled extensions under `dapr.ext.*`). Proto stubs (`dapr.proto.*`) have errors ignored, and unstubbed third-party libs (`langgraph.*`, `langchain.*`, `strands.*`, `strands_agents.*`, `grpc.aio`) are marked `ignore_missing_imports`. Configuration in `pyproject.toml` under `[tool.mypy]`.

## Commit and PR conventions

- **DCO required**: Every commit must include a `Signed-off-by` line. Use `git commit -s` to add it automatically.
- **CI checks**: Linting (ruff), unit tests (Python 3.10-3.14), type checking (mypy), and DCO verification run on all PRs.
- **Branch targets**: PRs go to `main` or `release-*` branches.
- **Tag-based releases**: A single `v*` tag triggers PyPI publishing for all packages (core SDK and all extensions).

## Agent task checklist

When completing any task on this project, work through this checklist. Not every item applies to every change — use judgment — but always consider each one.

### Before writing code

- [ ] Read the relevant existing source files before making changes
- [ ] Understand the existing patterns in the area you're modifying (naming, error handling, async vs sync)
- [ ] Check if there's both a sync and async variant that needs updating (see `dapr/aio/` and extension `aio/` subdirectories)
- [ ] Read the relevant extension's `AGENTS.md` for architecture and gotchas specific to that area

### Implementation

- [ ] Follow existing code style: single quotes, 100-char lines, Python 3.10+ syntax
- [ ] Do not edit files under `dapr/proto/` — these are auto-generated
- [ ] Do not add `__init__.py` files to namespace package roots in extensions

### Unit tests

- [ ] Add or update unit tests under `tests/` (core SDK) or `tests/ext/<name>/` (extensions)
- [ ] Tests are predominantly `unittest.TestCase`; follow the existing patterns in the relevant directory. A few pytest-style tests exist for fixture-dependent scenarios (e.g. `pytest.warns` for the `flask_dapr` shim).
- [ ] Verify tests pass: `uv run pytest -m "not e2e" ./tests --ignore=tests/integration --ignore=tests/examples` (must use pytest; `unittest discover` silently skips pytest-style tests)

### Linting and type checking

- [ ] Run `uv run ruff check --fix && uv run ruff format` and fix any remaining issues
- [ ] Run `uv run mypy` if you changed files covered by mypy (the `dapr` and `flask_dapr` packages, which includes all bundled extensions under `dapr.ext.*`)

### Examples (integration tests)

- [ ] If you added a new user-facing feature or building block, add or update an example in `examples/`
- [ ] Add a corresponding pytest test in `tests/examples/` (output-based) and/or `tests/integration/` (programmatic)
- [ ] If you changed output format of existing functionality, update expected output in `tests/examples/`
- [ ] See `examples/AGENTS.md` for full details on writing examples

### Documentation

- [ ] Update docstrings if you changed a public API's signature or behavior
- [ ] Update the relevant example README if the usage pattern changed

### Final verification

- [ ] Run `uv run ruff check --fix && uv run ruff format` — linting must be clean
- [ ] Run `uv run pytest -m "not e2e" ./tests --ignore=tests/integration --ignore=tests/examples` — all unit tests must pass
- [ ] If you touched examples: `uv run pytest tests/examples/test_<example-name>.py` to validate locally
- [ ] Commits must be signed off for DCO: `git commit -s`

## Important files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Package metadata, extras, dependencies, ruff, mypy, and uv workspace config |
| `uv.lock` | Locked dependency versions (reproducible installs) |
| `dapr/__init__.py` | Imports `_detect_legacy_extension_dists` to warn about legacy `dapr-ext-*` / `flask-dapr` installs that collide with the bundled extension files |
| `dapr/version/version.py` | SDK version string |
| `tests/examples/` | Output-based tests that validate examples by checking stdout |
| `tests/integration/` | Programmatic SDK tests using DaprClient directly |

## Gotchas

- **Namespace packages**: `dapr.ext` is a PEP 420 implicit namespace package. Do **not** create `dapr/ext/__init__.py`; that would block any future externally-published `dapr.ext.*` distribution from coexisting with the core wheel on install.
- **Proto files**: Never manually edit anything under `dapr/proto/`. These are generated.
- **Do not bump `grpcio-tools` like a normal dev dependency**: its pin must stay the version that generated the committed files under `dapr/proto/` — regenerating with a newer one raises the minimum `grpcio`/`protobuf` that SDK users can install, while leaving it alone is always safe. Dependabot is configured to ignore it; the comment in `.github/dependabot.yml` lists when a bump is justified and the 3-step recipe (pin + regen + floors, in one PR, enforced by `tests/test_proto_gencode_floor.py`).
- **Bundled extensions**: live under `dapr/ext/<name>/`, opted in via extras (`dapr[fastapi]`, etc.). The legacy `dapr-ext-*` and `flask-dapr` distributions are no longer published; legacy installs must be uninstalled before upgrading or `import dapr` will emit a `FutureWarning`.
- **DCO signoff**: PRs will be blocked by the DCO bot if commits lack `Signed-off-by`. Always use `git commit -s`.
- **Ruff version pinned**: `pyproject.toml` pins `ruff==0.14.1` in `[dependency-groups].dev`. Use `uv sync --all-packages --group dev` to get the exact version.
- **Examples are tested by output matching**: Changing output format (log messages, print statements) can break `tests/examples/`. Always check expected output there when modifying user-visible output.
- **Background processes in examples**: Examples that start background services (servers, subscribers) must include a cleanup step to stop them, or CI will hang.
- **Workflow is the most active area**: See `dapr/ext/workflow/AGENTS.md` for workflow-specific architecture and constraints.
