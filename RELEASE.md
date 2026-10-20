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

All `git` commands below use `upstream` to refer to the **canonical Dapr repository**
(`https://github.com/dapr/python-sdk`), not your personal fork.
If your local remote is named differently, substitute accordingly. The `gh` commands name the
repository with `--repo` instead.

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

### 4. Create the tag

Once the version bump PR on `release-X.Y` is merged, run the `dapr-python-release-tag`
workflow on `release-X.Y` (see [Creating the tag](#creating-the-tag)):

```bash
gh workflow run dapr-python-release-tag --repo dapr/python-sdk --ref release-X.Y -f version=X.Y.0rc0
```

The tag triggers the `dapr-python-release` workflow which builds and uploads
all packages to PyPI.

## Scenario B — Ship a new release candidate

Perform this when you want to publish `X.Y.0rcN` (N ≥ 1) from an existing `release-X.Y` branch.

### 1. Bump VERSION on the release branch

Open a PR **targeting `release-X.Y`** that changes `VERSION` from `X.Y.0rc(N-1)` → `X.Y.0rcN`.

### 2. Create the tag

Once the PR is merged:

```bash
gh workflow run dapr-python-release-tag --repo dapr/python-sdk --ref release-X.Y -f version=X.Y.0rcN
```

## Scenario C — Ship the stable release (and patch releases)

Perform this when `release-X.Y` is ready to ship a stable version — whether that is the
initial `X.Y.0` or a patch release (`X.Y.1`, `X.Y.2`, …).

### 1. Bump VERSION on the release branch

Open a PR **targeting `release-X.Y`** that drops the `rcN` suffix in `VERSION`:
`X.Y.ZrcN` → `X.Y.Z`.

### 2. Create the tag

Once the PR is merged:

```bash
gh workflow run dapr-python-release-tag --repo dapr/python-sdk --ref release-X.Y -f version=X.Y.Z
```

## Creating the tag

The `dapr-python-release-tag` workflow is the supported way to tag a release. Before it
creates `vX.Y.Z` at the tip of the selected branch, it runs `tools/check_release_version.py`,
which fails when:

- `VERSION` does not match the version you asked to release, which usually means the bump
  PR has not been merged yet;
- the branch is not `release-X.Y`, or `VERSION` belongs to a different `X.Y` series;
- `VERSION` is a `.dev` version;
- a tag for `VERSION` already exists.

You can run the same check locally before triggering the workflow, from an up-to-date checkout
of `release-X.Y` with all tags fetched:

```bash
git checkout release-X.Y && git pull upstream release-X.Y && git fetch upstream --tags
python tools/check_release_version.py --expected X.Y.Z --branch release-X.Y --require-untagged
```

The workflow runs the copy of itself found on the selected branch, so it only works on release
branches that contain `.github/workflows/release-tag.yaml` and `tools/check_release_version.py`.
Branches cut before these were added (`release-1.18` and older, and `release-1.19` until they are
backported) still tag by hand from the tip of the branch:
`git tag vX.Y.Z && git push upstream vX.Y.Z`.

A tag pushed by hand, or created through a GitHub Release, skips these checks. The publish
workflow still compares the tag to `VERSION` and refuses to upload on a mismatch. By then the
tag already exists, though, and has to be deleted and recreated once `VERSION` is fixed.

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
