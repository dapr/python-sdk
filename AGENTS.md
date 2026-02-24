# AGENTS.md — Dapr Python SDK

This file provides context for AI agents working on the Dapr Python SDK.
The project is the official Python SDK for [Dapr](https://dapr.io/) (Distributed Application Runtime),
enabling Python developers to build distributed applications using Dapr building blocks.

Repository: https://github.com/dapr/python-sdk
License: Apache 2.0

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
├── dapr-ext-grpc/           # gRPC App extension
├── dapr-ext-fastapi/        # FastAPI integration
├── dapr-ext-workflow/       # Workflow authoring
├── dapr-ext-langgraph/      # LangGraph checkpointer
├── dapr-ext-strands/        # Strands agent extension
└── flask_dapr/              # Flask integration

tests/                       # Unit tests (mirrors dapr/ package structure)
examples/                    # Example applications (each subfolder is self-contained)
docs/                        # Sphinx documentation source
tools/                       # Build and release scripts
```

## Key architectural patterns

- **Namespace packages**: The `dapr` namespace is shared across the core SDK and extensions using `find_namespace_packages`. Extensions live in `ext/` but install into the `dapr.ext.*` namespace.
- **Client architecture**: `DaprGrpcClient` (primary, high-performance) and HTTP-based clients. Both implement shared interfaces.
- **Actor model**: `Actor` base class, `ActorInterface` with `@actormethod` decorator, `ActorProxy`/`ActorProxyFactory` for client-side references, `ActorRuntime` for server-side hosting.
- **Serialization**: Pluggable via `Serializer` base class. `DefaultJSONSerializer` is the default.
- **Proto files**: Auto-generated from Dapr proto definitions. Never edit files under `dapr/proto/` directly.

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
# Run unit tests (replace 311 with your Python version)
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

## Examples (integration test suite)

The `examples/` directory serves as both user-facing documentation and the project's **integration test suite**. Each example is a self-contained application validated automatically in CI using [mechanical-markdown](https://pypi.org/project/mechanical-markdown/), which executes bash code blocks embedded in README files and asserts expected output.

### How example validation works

1. `examples/validate.sh` is the entry point — it `cd`s into an example directory and runs `mm.py -l README.md`
2. `mm.py` (mechanical-markdown) parses `<!-- STEP -->` HTML comment blocks in the README
3. Each STEP block wraps a bash code fence that gets executed
4. stdout/stderr is captured and checked against `expected_stdout_lines` / `expected_stderr_lines`
5. Validation fails if any expected output line is missing

Run examples locally (requires a running Dapr runtime via `dapr init`):

```bash
# All examples
tox -e examples

# Single example
tox -e example-component -- state_store

# Or directly
cd examples && ./validate.sh state_store
```

In CI (`validate_examples.yaml`), examples run against all supported Python versions (3.10-3.14) on Ubuntu with a full Dapr runtime environment including Docker, Redis, and (for LLM examples) Ollama.

### Example directory structure

Each example follows this pattern:

```
examples/<example-name>/
├── README.md              # Documentation + mechanical-markdown STEP blocks (REQUIRED)
├── *.py                   # Python application files
├── requirements.txt       # Dependencies (e.g., dapr>=1.17.0rc6)
├── components/            # Dapr component YAML configs (if needed)
│   ├── statestore.yaml
│   └── pubsub.yaml
├── config.yaml            # Dapr configuration (optional, e.g., for tracing/features)
└── proto/                 # Protobuf definitions (for gRPC examples)
```

Common Python file naming conventions:
- Server/receiver side: `*-receiver.py`, `subscriber.py`, `*_service.py`
- Client/caller side: `*-caller.py`, `publisher.py`, `*_client.py`
- Standalone: `state_store.py`, `crypto.py`, etc.

### Mechanical-markdown STEP block format

STEP blocks are HTML comments wrapping fenced bash code in the README:

````markdown
<!-- STEP
name: Run the example
expected_stdout_lines:
  - '== APP == Got state: value'
  - '== APP == State deleted'
background: false
sleep: 5
timeout_seconds: 30
output_match_mode: substring
match_order: none
-->

```bash
dapr run --app-id myapp --resources-path ./components/ python3 example.py
```

<!-- END_STEP -->
````

**STEP block attributes:**

| Attribute | Description |
|-----------|-------------|
| `name` | Descriptive name for the step |
| `expected_stdout_lines` | List of strings that must appear in stdout |
| `expected_stderr_lines` | List of strings that must appear in stderr |
| `background` | `true` to run in background (for long-running services) |
| `sleep` | Seconds to wait after starting before moving to the next step |
| `timeout_seconds` | Max seconds before the step is killed |
| `output_match_mode` | `substring` for partial matching (default is exact) |
| `match_order` | `none` if output lines can appear in any order |

**Tips for writing STEP blocks:**
- Use `background: true` with `sleep:` for services that need to stay running (servers, subscribers)
- Use `timeout_seconds:` to prevent CI hangs on broken examples
- Use `output_match_mode: substring` when output contains timestamps or dynamic content
- Use `match_order: none` when multiple concurrent operations produce unpredictable ordering
- Always include a cleanup step (e.g., `dapr stop`) when using background processes
- Make `expected_stdout_lines` specific enough to validate correctness, but not so brittle they break on cosmetic changes

### Dapr component YAML format

Components in `components/` directories follow the standard Dapr resource format:

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: statestore
spec:
  type: state.redis
  version: v1
  metadata:
  - name: redisHost
    value: localhost:6379
  - name: redisPassword
    value: ""
```

Common component types used in examples: `state.redis`, `pubsub.redis`, `lock.redis`, `configuration.redis`, `crypto.dapr.localstorage`, `bindings.*`.

### Adding a new example

1. Create a directory under `examples/` with a descriptive kebab-case name
2. Add Python source files and a `requirements.txt` referencing the needed SDK packages
3. Add Dapr component YAMLs in a `components/` subdirectory if the example uses state, pubsub, etc.
4. Write a `README.md` with:
   - Introduction explaining what the example demonstrates
   - Pre-requisites section
   - Install instructions
   - Running instructions with `<!-- STEP -->` blocks wrapping the `dapr run` commands
   - Expected output section
   - Cleanup step to stop background processes
5. Register the example in `tox.ini` under `[testenv:examples]` commands:
   ```
   ./validate.sh your-example-name
   ```
6. Test locally: `cd examples && ./validate.sh your-example-name`

## Common tasks

### Adding a new feature to the core SDK

1. Implement in the appropriate module under `dapr/`
2. Add unit tests under `tests/` mirroring the package structure
3. Run `tox -e ruff` to fix formatting
4. Run `tox -e py311` (or your Python version) to verify tests pass
5. Run `tox -e type` to check types if you modified typed modules

### Adding or modifying an extension

1. Each extension in `ext/` has its own `setup.cfg`, `setup.py`, and `tests/` directory
2. The extension installs into the `dapr.ext.*` namespace
3. Update the extension's `setup.cfg` if adding new dependencies
4. Add tests under the extension's own `tests/` folder
5. The extension must be added to `tox.ini` commands if not already present

### Updating proto/gRPC stubs

Files under `dapr/proto/` are auto-generated. Do not edit them directly. Regeneration is handled by build tooling from upstream Dapr proto definitions.

## Agent task checklist

When completing any task on this project, work through this checklist to make sure nothing is missed. Not every item applies to every change — use judgment — but always consider each one.

### Before writing code

- [ ] Read the relevant existing source files before making changes
- [ ] Understand the existing patterns in the area you're modifying (naming, error handling, async vs sync)
- [ ] Check if there's both a sync and async variant that needs updating (see `dapr/aio/` and `dapr/clients/http/` for async counterparts)

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
| `examples/*/README.md` | Example docs with embedded integration test steps |

## Gotchas

- **Namespace packages**: Do not add `__init__.py` to the top-level `dapr/` directory in extensions — it will break namespace package resolution.
- **Proto files**: Never manually edit anything under `dapr/proto/`. These are generated.
- **Extension independence**: Each extension is a separate PyPI package. Core SDK changes should not break extensions; extension changes should not require core SDK changes unless intentional.
- **DCO signoff**: PRs will be blocked by the DCO bot if commits lack `Signed-off-by`. Always use `git commit -s`.
- **Ruff version pinned**: Dev requirements pin `ruff === 0.14.1`. Use this exact version to match CI.
- **Examples are integration tests**: Changing output format (log messages, print statements) can break example validation. Always check `expected_stdout_lines` in example READMEs when modifying user-visible output.
- **Background processes in examples**: Examples that start background services (servers, subscribers) must include a cleanup step to stop them, or CI will hang.
