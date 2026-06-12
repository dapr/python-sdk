# Release process

This document describes the release process for the Dapr Python SDK.

A single tag (`v*`) triggers the release of the core SDK only:

| PyPI package | Notes |
|---|---|
| `dapr` (core SDK) | Includes every extension under `dapr.ext.*`. Users opt in to per-extension third-party deps via extras: `pip install "dapr[fastapi]"`, etc. The legacy top-level `flask_dapr` import path remains available as a thin shim inside this wheel and emits `FutureWarning`. |

**As of 1.19, the previously-separate distributions** — `dapr-ext-fastapi`, `dapr-ext-grpc`,
`dapr-ext-langgraph`, `dapr-ext-strands`, `dapr-ext-workflow`, `flask-dapr` —
are **no longer published**. Backport branches that predate 1.19 (`release-1.18`,
`release-1.17`) still build and publish them for fixes shipped to those releases.

The design constraint was keeping `from dapr.ext.X import ...` stable across
the upgrade, so the cost lands once in pip during migration rather than
forever in every existing codebase that already imports those paths.

The price: legacy dists on disk now claim the same files core `dapr` ships,
and pip has no cross-dist ownership awareness. `pip uninstall <legacy>` walks
the legacy RECORD and deletes `dapr/ext/<name>/*.py` from disk, leaving a
silently broken install: `pip show dapr` reports 1.19 installed, but
`from dapr.ext.<name> import ...` raises `ModuleNotFoundError`. The recipe
below uses `--force-reinstall --no-deps dapr` to rewrite those files after
the legacy uninstall removes them.

Republishing the legacy distributions as `dapr-ext-name` shims depending on
`dapr[name]` was considered and rejected: any shim that doesn't ship the
actual files leaves the legacy version's RECORD on disk in existing
environments, so the same uninstall failure mode remains. They would also
add a per-extension release artifact to maintain in perpetuity.

Existing installs must migrate explicitly:

```sh
pip uninstall -y dapr-ext-fastapi dapr-ext-grpc dapr-ext-langgraph dapr-ext-strands dapr-ext-workflow flask-dapr
pip install --force-reinstall --no-deps dapr
pip install "dapr[<extras>]"
```

`--force-reinstall --no-deps dapr` rewrites the `dapr/ext/<name>/` files the
legacy uninstall removed; keeping it separate from the extras install avoids
churning user-pinned versions of fastapi, uvicorn, langchain, etc.
`dapr/__init__.py` detects both the legacy-installed and post-uninstall
states at import time and prints the recovery command as a `FutureWarning`.
Suppress with `DAPR_SKIP_LEGACY_CHECK=1`.

The warning and the `flask_dapr` shim are kept through 1.21 and removed in
1.22. 1.18 is the last release to ship the standalone distributions, and N-2
support keeps it alive until 1.21, so this window covers every user who could
still be migrating.

You can also create the tag via a **GitHub Release**, which auto-creates the tag and provides
a changelog UI.

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
           simultaneously on main:
           - versions (prev).dev → X.Y.0.dev
```

Only tag pushes (`v*`) publish to PyPI. Pushes to `main` and release branches
do not publish anything.

Users who need the development builds can install from git
(see the [README](./README.md#install-dapr-python-sdk)).

## Version file

A single `VERSION` file at the repo root is the source of truth for all
the packages. Each package's `pyproject.toml` reads from it.

## Version string conventions

| Stage                              | `VERSION` example             |
| ---------------------------------- | ----------------------------- |
| Development (always on `main`)     | `X.Y.0.dev`                   |
| First RC (on `release-X.Y`)        | `X.Y.0rc0`                    |
| Subsequent RCs (on `release-X.Y`)  | `X.Y.0rc1`, `X.Y.0rc2`, …     |
| Stable release                     | `X.Y.0`                       |
| Patch release candidate            | `X.Y.1rc1`                    |
| Stable patch release               | `X.Y.1`                       |

`X.Y` is the major.minor of the release line you're working on (the branch
name `release-X.Y` matches). `main` always carries the **next** un-released
minor as `.dev` — once `release-X.Y` is forked, `main` advances from
`X.Y.0.dev` to the next minor's `.dev` (e.g. `X.(Y+1).0.dev`).

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

### 2. Bump VERSION on the release branch (first commit)

On the newly created `release-X.Y` branch, open a PR **targeting `release-X.Y`** that
changes the `VERSION` file from `X.Y.0.dev` → `X.Y.0rc0`.

### 3. Bump VERSION on `main` (second commit)

Open a PR targeting `main` that changes `VERSION` from the previous dev version to
`X.Y.0.dev`.

### 4. Push the tag

Once the version bump PR on `release-X.Y` is merged, create and push the tag from the
**tip of `release-X.Y`**:

```bash
git checkout release-X.Y
git pull upstream release-X.Y

git tag vX.Y.0rc0 && git push upstream vX.Y.0rc0
```

The tag push triggers the `dapr-python-release` workflow which builds and uploads
all packages to PyPI.

## Scenario B — Ship a new release candidate

Perform this when you want to publish `X.Y.0rcN` (N ≥ 1) from an existing `release-X.Y` branch.

### 1. Bump VERSION on the release branch

Open a PR **targeting `release-X.Y`** that changes `VERSION` from `X.Y.0rc(N-1)` → `X.Y.0rcN`.

### 2. Push the tag

Once the PR is merged:

```bash
git checkout release-X.Y
git pull upstream release-X.Y

git tag vX.Y.0rcN && git push upstream vX.Y.0rcN
```

## Scenario C — Ship the stable release (and patch releases)

Perform this when `release-X.Y` is ready to ship a stable version — whether that is the
initial `X.Y.0` or a patch release (`X.Y.1`, `X.Y.2`, …).

### 1. Bump VERSION on the release branch

Open a PR **targeting `release-X.Y`** that drops the `rcN` suffix in `VERSION`:
`X.Y.ZrcN` → `X.Y.Z`.

### 2. Push the tag

Once the PR is merged:

```bash
git checkout release-X.Y
git pull upstream release-X.Y

git tag vX.Y.Z && git push upstream vX.Y.Z
```

Alternatively, create a **GitHub Release** targeting `release-X.Y` with tag `vX.Y.Z` — this
creates the tag and triggers the publish workflow automatically.

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
