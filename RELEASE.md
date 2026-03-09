# Release process

This document describes the release process for the Dapr Python SDK.
It covers all packages published from this repository:

| Tag prefix | PyPI package |
|---|---|
| `v*` | `dapr` (core SDK) |
| `workflow-v*` | `dapr-ext-workflow` |
| `grpc-v*` | `dapr-ext-grpc` |
| `fastapi-v*` | `dapr-ext-fastapi` |
| `flask-v*` | `flask_dapr` |
| `langgraph-v*` | `dapr-ext-langgraph` |
| `strands-v*` | `dapr-ext-strands` |

## Overview

Releases follow a branching model where `main` is always the development trunk.
When a version is ready to enter stabilisation, a `release-X.Y` branch is forked from `main`.
From that point on, all changes land in `main` first and are backported to the release branch
as needed. Release candidates and the final stable release are all cut from that branch.

```
main         ──●──●──●──●──●──●──●──●──●──●──▶
                │  (prev).dev  X.Y.0.dev
                │  (fork)    ↑
release-X.Y     ●──●────●───●───●───●──▶
                │       ↑       ↑   ↑
                │     rc0     rc1  X.Y.0
                │
           first commit on release-X.Y:
           - versions (prev).dev → X.Y.0rc0
           - dapr deps >=(prev).dev → >=X.Y.0rc0
           simultaneously on main:
           - versions (prev).dev → X.Y.0.dev
           - dapr deps >=(prev).dev → >=X.Y.0.dev
```

## Version files

Every package in this repository has one version file and, for extensions, one `setup.cfg`
dependency line that must be kept in sync during a release.

**Version files** (set `__version__`):
- `dapr/version/version.py`
- `ext/dapr-ext-workflow/dapr/ext/workflow/version.py`
- `ext/dapr-ext-grpc/dapr/ext/grpc/version.py`
- `ext/dapr-ext-fastapi/dapr/ext/fastapi/version.py`
- `ext/dapr-ext-langgraph/dapr/ext/langgraph/version.py`
- `ext/dapr-ext-strands/dapr/ext/strands/version.py`
- `ext/flask_dapr/flask_dapr/version.py`

**Dependency lower bounds** in extension `setup.cfg` files (each has `dapr >= <version>`):
- `ext/dapr-ext-workflow/setup.cfg`
- `ext/dapr-ext-grpc/setup.cfg`
- `ext/dapr-ext-fastapi/setup.cfg`
- `ext/dapr-ext-langgraph/setup.cfg`
- `ext/dapr-ext-strands/setup.cfg`
- `ext/flask_dapr/setup.cfg`

## Version string conventions

| Stage | `__version__` example | dep lower bound example |
|---|---|---|
| Development (always on `main`) | `1.17.0.dev` | `dapr >= 1.17.0.dev` |
| First RC (on `release-X.Y`) | `1.17.0rc0` | `dapr >= 1.17.0rc0` |
| Subsequent RCs (on `release-X.Y`) | `1.17.0rc1`, `1.17.0rc2`, … | `dapr >= 1.17.0rc1` |
| Stable release | `1.17.0` | `dapr >= 1.17.0` |
| Patch release candidate | `1.17.1rc1` | `dapr >= 1.17.1rc1` |
| Stable patch release | `1.17.1` | `dapr >= 1.17.1` |

## Remote convention

All commands below use `upstream` to refer to the **canonical Dapr repository**
(`https://github.com/dapr/python-sdk`), not your personal fork.
If your local remote is named differently, substitute accordingly.

## Scenario A — Fork a new release branch

Perform this when the current `main` is ready to start the stabilisation cycle for version X.Y.

### 1. Create the branch

```bash
git checkout main
git pull upstream main
git checkout -b release-X.Y
git push upstream release-X.Y
```

### 2. Bump versions on the release branch (first commit)

On the newly created `release-X.Y` branch, open a PR **targeting `release-X.Y`** that does:

- In all seven version files: change `X.Y.0.dev` → `X.Y.0rc0`
- In all six extension `setup.cfg` files: change `dapr >= X.Y.0.dev` → `dapr >= X.Y.0rc0`

### 3. Bump versions on `main` (second commit)

Open a PR targeting `main` to align it with the new release version:

- In all seven version files: change the previous dev version to `X.Y.0.dev`
- In all six extension `setup.cfg` files: change the previous `dapr >= ...dev` to `dapr >= X.Y.0.dev`

### 4. Push the tags

Once the version bump PR on `release-X.Y` is merged, create and push the tags from the
**tip of `release-X.Y`**:

```bash
git checkout release-X.Y
git pull upstream release-X.Y

git tag vX.Y.0rc0            && git push upstream vX.Y.0rc0
git tag workflow-vX.Y.0rc0   && git push upstream workflow-vX.Y.0rc0
git tag grpc-vX.Y.0rc0       && git push upstream grpc-vX.Y.0rc0
git tag flask-vX.Y.0rc0      && git push upstream flask-vX.Y.0rc0
git tag fastapi-vX.Y.0rc0    && git push upstream fastapi-vX.Y.0rc0
git tag langgraph-vX.Y.0rc0  && git push upstream langgraph-vX.Y.0rc0
git tag strands-vX.Y.0rc0    && git push upstream strands-vX.Y.0rc0
```

Each tag push triggers the `dapr-python-release` workflow which builds and uploads the
corresponding package to PyPI.

## Scenario B — Ship a new release candidate

Perform this when you want to publish `X.Y.0rcN` (N ≥ 1) from an existing `release-X.Y` branch.

### 1. Bump versions on the release branch

Open a PR **targeting `release-X.Y`** that does:

- In all seven version files: change `X.Y.0rc(N-1)` → `X.Y.0rcN`
- In all six extension `setup.cfg` files: change `dapr >= X.Y.0rc(N-1)` → `dapr >= X.Y.0rcN`

### 2. Push the tags

Once the PR is merged:

```bash
git checkout release-X.Y
git pull upstream release-X.Y

git tag vX.Y.0rcN            && git push upstream vX.Y.0rcN
git tag workflow-vX.Y.0rcN   && git push upstream workflow-vX.Y.0rcN
git tag grpc-vX.Y.0rcN       && git push upstream grpc-vX.Y.0rcN
git tag flask-vX.Y.0rcN      && git push upstream flask-vX.Y.0rcN
git tag fastapi-vX.Y.0rcN    && git push upstream fastapi-vX.Y.0rcN
git tag langgraph-vX.Y.0rcN  && git push upstream langgraph-vX.Y.0rcN
git tag strands-vX.Y.0rcN    && git push upstream strands-vX.Y.0rcN
```

## Scenario C — Ship the stable release (and patch releases)

Perform this when `release-X.Y` is ready to ship a stable version — whether that is the
initial `X.Y.0` or a patch release (`X.Y.1`, `X.Y.2`, …).

### 1. Bump versions on the release branch

Open a PR **targeting `release-X.Y`** that does:

- In all seven version files: change `X.Y.ZrcN` → `X.Y.Z` (drop the `rcN` suffix)
- In all six extension `setup.cfg` files: change `dapr >= X.Y.ZrcN` → `dapr >= X.Y.Z`

### 2. Push the tags

Once the PR is merged:

```bash
git checkout release-X.Y
git pull upstream release-X.Y

git tag vX.Y.Z            && git push upstream vX.Y.Z
git tag workflow-vX.Y.Z   && git push upstream workflow-vX.Y.Z
git tag grpc-vX.Y.Z       && git push upstream grpc-vX.Y.Z
git tag flask-vX.Y.Z      && git push upstream flask-vX.Y.Z
git tag fastapi-vX.Y.Z    && git push upstream fastapi-vX.Y.Z
git tag langgraph-vX.Y.Z  && git push upstream langgraph-vX.Y.Z
git tag strands-vX.Y.Z    && git push upstream strands-vX.Y.Z
```

## Backporting changes

Bug fixes and small improvements that should appear in both `main` and an active release
branch are backported automatically.

1. Open your PR targeting `main` as usual.
2. Once merged, add a label of the form `backport release-X.Y` to the PR.
   The [backport workflow](.github/workflows/backport.yaml) will open a new PR against
   `release-X.Y` automatically.
3. Review and merge the backport PR on `release-X.Y`.

You can also add the label before merging; the workflow will start once the PR is closed
as merged.

> The backport workflow can target any `release-*` branch, so patches can be applied to
> older releases if needed.
