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
dapr/                        # Core SDK package
├── actor/                   # Actor framework (virtual actor model)
├── aio/                     # Async I/O modules
├── clients/                 # Dapr clients (gRPC and HTTP)
├── common/                  # Shared utilities
├── conf/                    # Configuration (settings, environment)
├── proto/                   # Auto-generated gRPC protobuf stubs (DO NOT EDIT)
├── serializers/             # JSON and pluggable serializers
└── version/                 # Version metadata

ext/                         # Extension packages (each is a separate PyPI package)
├── dapr-ext-workflow/       # Workflow authoring  ← see ext/dapr-ext-workflow/AGENTS.md
├── dapr-ext-grpc/           # gRPC App extension  ← see ext/dapr-ext-grpc/AGENTS.md
├── dapr-ext-fastapi/        # FastAPI integration  ← see ext/dapr-ext-fastapi/AGENTS.md
├── dapr-ext-langgraph/      # LangGraph checkpointer  ← see ext/dapr-ext-langgraph/AGENTS.md
├── dapr-ext-strands/        # Strands agent sessions  ← see ext/dapr-ext-strands/AGENTS.md
└── flask_dapr/              # Flask integration  ← see ext/flask_dapr/AGENTS.md

tests/                       # Unit tests (mirrors dapr/ package structure)
examples/                    # Integration test suite  ← see examples/AGENTS.md
docs/                        # Sphinx documentation source
tools/                       # Build and release scripts
```

## Key architectural patterns

- **Namespace packages**: The `dapr` namespace is shared across the core SDK and extensions via `find_namespace_packages`. Extensions live in `ext/` but install into the `dapr.ext.*` namespace. Do not add `__init__.py` to namespace package roots in extensions.
- **Client architecture**: `DaprGrpcClient` (primary, high-performance) and HTTP-based clients. Both implement shared interfaces.
- **Actor model**: `Actor` base class, `ActorInterface` with `@actormethod` decorator, `ActorProxy`/`ActorProxyFactory` for client-side references, `ActorRuntime` for server-side hosting.
- **Serialization**: Pluggable via `Serializer` base class. `DefaultJSONSerializer` is the default.
- **Proto files**: Auto-generated from Dapr proto definitions. Never edit files under `dapr/proto/` directly.

## Extension overview

Each extension is a **separate PyPI package** with its own `setup.cfg`, `setup.py`, `tests/`, and `AGENTS.md`.

| Extension | Package | Purpose | Active development |
|-----------|---------|---------|-------------------|
| `dapr-ext-workflow` | `dapr.ext.workflow` | Durable workflow orchestration via durabletask-dapr | **High** — major focus area |
| `dapr-ext-grpc` | `dapr.ext.grpc` | gRPC server for Dapr callbacks (methods, pub/sub, bindings, jobs) | Moderate |
| `dapr-ext-fastapi` | `dapr.ext.fastapi` | FastAPI integration for pub/sub and actors | Moderate |
| `flask_dapr` | `flask_dapr` | Flask integration for pub/sub and actors | Low |
| `dapr-ext-langgraph` | `dapr.ext.langgraph` | LangGraph checkpoint persistence to Dapr state store | Moderate |
| `dapr-ext-strands` | `dapr.ext.strands` | Strands agent session management via Dapr state store | New |

## Examples (integration test suite)

The `examples/` directory serves as both user-facing documentation and the project's integration test suite. Examples are validated in CI using [mechanical-markdown](https://pypi.org/project/mechanical-markdown/), which executes bash code blocks from README files and asserts expected output.

**See `examples/AGENTS.md`** for the full guide on example structure, validation, mechanical-markdown STEP blocks, and how to add new examples.

Quick reference:
```bash
tox -e examples                          # Run all examples (needs Dapr runtime)
tox -e example-component -- state_store  # Run a single example
cd examples && ./validate.sh state_store # Run directly
```

## Python version support

- **Minimum**: Python 3.10
- **Tested**: 3.10, 3.11, 3.12, 3.13, 3.14
- **Target version for tooling**: `py310` (ruff, mypy)

## Development setup

Install all packages in editable mode with dev dependencies:

```bash
pip install -r dev-requirements.txt \
    -e . \
    -e ext/dapr-ext-workflow/ \
    -e ext/dapr-ext-grpc/ \
    -e ext/dapr-ext-fastapi/ \
    -e ext/dapr-ext-langgraph/ \
    -e ext/dapr-ext-strands/ \
    -e ext/flask_dapr/
```

## Running tests

Tests use Python's built-in `unittest` framework with `coverage`. Run via tox:

```bash
# Run all unit tests (replace 311 with your Python version)
tox -e py311

# Run linting and formatting
tox -e ruff

# Run type checking
tox -e type

# Validate examples (requires Dapr runtime)
tox -e examples
```

To run tests directly without tox:

```bash
# Core SDK tests
python -m unittest discover -v ./tests

# Extension tests (run each separately)
python -m unittest discover -v ./ext/dapr-ext-workflow/tests
python -m unittest discover -v ./ext/dapr-ext-grpc/tests
python -m unittest discover -v ./ext/dapr-ext-fastapi/tests
python -m unittest discover -v ./ext/dapr-ext-langgraph/tests
python -m unittest discover -v ./ext/dapr-ext-strands/tests
python -m unittest discover -v ./ext/flask_dapr/tests
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
ruff check --fix
ruff format
```

**Type checking**: MyPy

```bash
mypy --config-file mypy.ini
```

MyPy is configured to check: `dapr/actor/`, `dapr/clients/`, `dapr/conf/`, `dapr/serializers/`, `ext/dapr-ext-grpc/`, `ext/dapr-ext-fastapi/`, `ext/flask_dapr/`, and `examples/demo_actor/`. Proto stubs (`dapr.proto.*`) have errors ignored.

## Commit and PR conventions

- **DCO required**: Every commit must include a `Signed-off-by` line. Use `git commit -s` to add it automatically.
- **CI checks**: Linting (ruff), unit tests (Python 3.10-3.14), type checking (mypy), and DCO verification run on all PRs.
- **Branch targets**: PRs go to `main` or `release-*` branches.
- **Tag-based releases**: Tags like `v*`, `workflow-v*`, `grpc-v*`, `fastapi-v*`, `flask-v*`, `langgraph-v*`, `strands-v*` trigger PyPI publishing for the corresponding package.

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

- [ ] Add or update unit tests under `tests/` (core SDK) or `ext/*/tests/` (extensions)
- [ ] Tests use `unittest` — follow the existing test patterns in the relevant directory
- [ ] Verify tests pass: `python -m unittest discover -v ./tests` (or the relevant test directory)

### Linting and type checking

- [ ] Run `ruff check --fix && ruff format` and fix any remaining issues
- [ ] Run `mypy --config-file mypy.ini` if you changed files covered by mypy (actor, clients, conf, serializers, ext-grpc, ext-fastapi, flask_dapr)

### Examples (integration tests)

- [ ] If you added a new user-facing feature or building block, add or update an example in `examples/`
- [ ] Ensure the example README has `<!-- STEP -->` blocks with `expected_stdout_lines` so it is validated in CI
- [ ] If you added a new example, register it in `tox.ini` under `[testenv:examples]`
- [ ] If you changed output format of existing functionality, update `expected_stdout_lines` in affected example READMEs
- [ ] See `examples/AGENTS.md` for full details on writing examples

### Documentation

- [ ] Update docstrings if you changed a public API's signature or behavior
- [ ] Update the relevant example README if the usage pattern changed

### Final verification

- [ ] Run `tox -e ruff` — linting must be clean
- [ ] Run `tox -e py311` (or your Python version) — all unit tests must pass
- [ ] If you touched examples: `tox -e example-component -- <example-name>` to validate locally
- [ ] Commits must be signed off for DCO: `git commit -s`

## Important files

| File | Purpose |
|------|---------|
| `setup.cfg` | Core package metadata and dependencies |
| `setup.py` | Package build script (handles dev version suffixing) |
| `pyproject.toml` | Ruff configuration |
| `tox.ini` | Test environments and CI commands |
| `mypy.ini` | Type checking configuration |
| `dev-requirements.txt` | Development/test dependencies |
| `dapr/version/__init__.py` | SDK version string |
| `ext/*/setup.cfg` | Extension package metadata and dependencies |
| `examples/validate.sh` | Entry point for mechanical-markdown example validation |

## Gotchas

- **Namespace packages**: Do not add `__init__.py` to the top-level `dapr/` directory in extensions — it will break namespace package resolution.
- **Proto files**: Never manually edit anything under `dapr/proto/`. These are generated.
- **Extension independence**: Each extension is a separate PyPI package. Core SDK changes should not break extensions; extension changes should not require core SDK changes unless intentional.
- **DCO signoff**: PRs will be blocked by the DCO bot if commits lack `Signed-off-by`. Always use `git commit -s`.
- **Ruff version pinned**: Dev requirements pin `ruff === 0.14.1`. Use this exact version to match CI.
- **Examples are integration tests**: Changing output format (log messages, print statements) can break example validation. Always check `expected_stdout_lines` in example READMEs when modifying user-visible output.
- **Background processes in examples**: Examples that start background services (servers, subscribers) must include a cleanup step to stop them, or CI will hang.
- **Workflow is the most active area**: See `ext/dapr-ext-workflow/AGENTS.md` for workflow-specific architecture and constraints.
