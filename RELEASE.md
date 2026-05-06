# Release process

This document describes the release process for the Dapr Python SDK.

A single tag (`v*`) triggers the release of **all packages** published from this repository:

| PyPI package |
|---|
| `dapr` (core SDK) |
| `dapr-ext-workflow` |
| `dapr-ext-grpc` |
| `dapr-ext-fastapi` |
| `flask_dapr` |
| `dapr-ext-langgraph` |
| `dapr-ext-strands` |

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

## Version files

Every package in this repository has one version file.

**Version files** (set `__version__`):
- `dapr/version/version.py`
- `ext/dapr-ext-workflow/dapr/ext/workflow/version.py`
- `ext/dapr-ext-grpc/dapr/ext/grpc/version.py`
- `ext/dapr-ext-fastapi/dapr/ext/fastapi/version.py`
- `ext/dapr-ext-langgraph/dapr/ext/langgraph/version.py`
- `ext/dapr-ext-strands/dapr/ext/strands/version.py`
- `ext/flask_dapr/flask_dapr/version.py`

## Version string conventions

| Stage                              | `__version__` example         |
| ---------------------------------- | ----------------------------- |
| Development (always on `main`)     | `1.18.0.dev`                  |
| First RC (on `release-X.Y`)        | `1.18.0rc0`                   |
| Subsequent RCs (on `release-X.Y`)  | `1.18.0rc1`, `1.18.0rc2`, …   |
| Stable release                     | `1.18.0`                      |
| Patch release candidate            | `1.18.1rc1`                   |
| Stable patch release               | `1.18.1`                      |

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

On the newly created `release-X.Y` branch, open a PR **targeting `release-X.Y`** that
changes `X.Y.0.dev` → `X.Y.0rc0` in all the version files.

### 3. Bump versions on `main` (second commit)

Open a PR targeting `main` that changes the previous dev version to `X.Y.0.dev` in all
the version files. 

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

### 1. Bump versions on the release branch

Open a PR **targeting `release-X.Y`** that changes `X.Y.0rc(N-1)` → `X.Y.0rcN` in all
the version files.

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

### 1. Bump versions on the release branch

Open a PR **targeting `release-X.Y`** that drops the `rcN` suffix in all the version
files: `X.Y.ZrcN` → `X.Y.Z`.

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
