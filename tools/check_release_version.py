# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Checks that the VERSION file is ready to be released.

The release-tag workflow runs this before it creates a tag, so a release branch
whose VERSION was never bumped fails before any tag exists. The publish
workflow runs it again on the tag itself before uploading to PyPI.

Usage:
    python tools/check_release_version.py --expected 1.19.0rc2 \
        --branch release-1.19 --require-untagged
    python tools/check_release_version.py --tag v1.19.0rc2
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = REPO_ROOT / 'VERSION'
TAG_PREFIX = 'v'
TAG_REF_PREFIX = 'refs/tags/'
BRANCH_REF_PREFIX = 'refs/heads/'
RELEASE_DOC_HINT = 'See RELEASE.md.'
GIT_TIMEOUT_SECONDS = 30

# Only PEP 440-normalized stable or rc versions, so the tag, the VERSION file
# and the wheel metadata all spell the version identically.
RELEASE_VERSION_PATTERN = re.compile(r'(?P<series>\d+\.\d+)\.\d+(?:rc\d+)?')
RELEASE_BRANCH_PATTERN = re.compile(r'release-(?P<series>\d+\.\d+)')

logger = logging.getLogger('check_release_version')


class ReleaseVersionError(Exception):
    """Raised when VERSION is not ready for the requested release."""


def read_version(version_path: Path = VERSION_FILE) -> str:
    """Returns the version string stored in the VERSION file."""
    return version_path.read_text(encoding='utf-8').strip()


def strip_tag_prefix(tag: str) -> str:
    """Turns `refs/tags/v1.2.3` or `v1.2.3` into `1.2.3`."""
    return tag.removeprefix(TAG_REF_PREFIX).removeprefix(TAG_PREFIX)


def check_release_version(version: str) -> None:
    """Fails unless the version is a stable or rc release, never a .dev one."""
    if RELEASE_VERSION_PATTERN.fullmatch(version):
        return
    raise ReleaseVersionError(
        f'VERSION {version!r} is not a releasable version. Release tags must point to a '
        f'stable (X.Y.Z) or rc (X.Y.ZrcN) version, never .dev. {RELEASE_DOC_HINT}'
    )


def check_expected_version(version: str, expected: str) -> None:
    """Fails unless VERSION holds the version the maintainer intends to release."""
    expected_version = strip_tag_prefix(expected)
    if version == expected_version:
        return
    raise ReleaseVersionError(
        f'Releasing {expected_version!r} but VERSION is {version!r}. Bump VERSION to '
        f'{expected_version!r} on the release branch and merge that first. {RELEASE_DOC_HINT}'
    )


def check_branch(version: str, branch: str) -> None:
    """Fails unless the branch is release-X.Y and VERSION belongs to the X.Y series."""
    branch_name = branch.removeprefix(BRANCH_REF_PREFIX)
    branch_match = RELEASE_BRANCH_PATTERN.fullmatch(branch_name)
    if branch_match is None:
        raise ReleaseVersionError(
            f'Releases are cut from release-X.Y branches, not {branch_name!r}. {RELEASE_DOC_HINT}'
        )
    version_match = RELEASE_VERSION_PATTERN.fullmatch(version)
    version_series = version_match['series'] if version_match else None
    if version_series == branch_match['series']:
        return
    raise ReleaseVersionError(
        f'VERSION {version!r} does not belong on {branch_name!r}. {RELEASE_DOC_HINT}'
    )


def check_tag(version: str, tag: str) -> None:
    """Fails unless the tag names exactly the version in VERSION."""
    tag_version = strip_tag_prefix(tag)
    if version == tag_version:
        return
    raise ReleaseVersionError(
        f'Tag {tag!r} expects version={tag_version!r}, got {version!r}. '
        f'Bump VERSION before tagging. {RELEASE_DOC_HINT}'
    )


def check_untagged(version: str, existing_tags: Iterable[str]) -> None:
    """Fails if VERSION was already released, which means it was never bumped."""
    release_tag = f'{TAG_PREFIX}{version}'
    if release_tag not in set(existing_tags):
        return
    raise ReleaseVersionError(
        f'Tag {release_tag!r} already exists, so VERSION {version!r} has already been '
        f'released. Bump VERSION to the next version first. {RELEASE_DOC_HINT}'
    )


def list_git_tags() -> set[str]:
    """Returns every tag known to the local clone."""
    git_result = subprocess.run(
        ['git', 'tag', '--list'],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    return set(git_result.stdout.split())


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[1] if __doc__ else None)
    parser.add_argument('--version-file', type=Path, default=VERSION_FILE)
    parser.add_argument('--expected', help='version the maintainer intends to release')
    parser.add_argument('--branch', help='release branch the tag will be cut from')
    parser.add_argument('--tag', help='tag that triggered the release')
    parser.add_argument(
        '--require-untagged',
        action='store_true',
        help='fail if a tag for VERSION already exists in the local clone',
    )
    return parser.parse_args(argv)


def run_checks(args: argparse.Namespace) -> str:
    """Runs every check the arguments ask for and returns the validated version."""
    version = read_version(args.version_file)
    check_release_version(version)
    if args.expected:
        check_expected_version(version, args.expected)
    if args.branch:
        check_branch(version, args.branch)
    if args.tag:
        check_tag(version, args.tag)
    if args.require_untagged:
        check_untagged(version, list_git_tags())
    return version


def configure_logging() -> None:
    # Inside GitHub Actions, ::error:: surfaces the message on the run summary.
    in_github_actions = os.environ.get('GITHUB_ACTIONS') == 'true'
    log_format = '::error::%(message)s' if in_github_actions else '%(levelname)s: %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, stream=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        version = run_checks(args)
    except ReleaseVersionError as error:
        logger.error('%s', error)
        return 1
    logger.info('VERSION %s is ready to release', version)
    return 0


if __name__ == '__main__':
    configure_logging()
    sys.exit(main())
