#!/usr/bin/env python3
"""Build a GitHub Actions matrix for Dapr runtime compatibility testing.

Derives runtime minors N, N-1, N-2 from the SDK VERSION file, resolves the
latest patch (or RC) per minor from dapr/dapr GitHub releases, and emits a
matrix of Python version × runtime version pairs for CI.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DAPR_RELEASES_URL = 'https://api.github.com/repos/dapr/dapr/releases?per_page=100'
DEFAULT_PYTHON_VERSIONS = ('3.10', '3.11', '3.12', '3.13', '3.14')
COMPAT_RUNTIME_COUNT = 3
DEFAULT_VERSION_FILE = Path('VERSION')
GITHUB_OUTPUT_ENV = 'GITHUB_OUTPUT'
GITHUB_TOKEN_ENV = 'GITHUB_TOKEN'
MATRIX_OUTPUT_KEY = 'matrix'


def parse_sdk_version(sdk_version: str) -> tuple[int, int]:
    """Return major and minor integers from an SDK version string."""
    base_version = sdk_version.split('.dev', maxsplit=1)[0]
    major_text, minor_text, *_ = base_version.split('.')
    return int(major_text), int(minor_text)


def runtime_minors_from_sdk(major: int, minor: int, count: int = COMPAT_RUNTIME_COUNT) -> list[str]:
    """Return Dapr runtime minor strings for N .. N-(count-1)."""
    return [f'{major}.{minor - offset}' for offset in range(count)]


def version_key(version: str) -> tuple[int, ...]:
    """Sort key for Dapr runtime version strings including RC suffixes."""
    base_version, _, suffix = version.partition('-')
    parts = tuple(int(part) for part in base_version.split('.'))
    if suffix.startswith('rc.'):
        return parts + (int(suffix.removeprefix('rc.')),)
    return parts


def latest_patch_for_minor(releases: list[dict[str, Any]], runtime_minor: str) -> str | None:
    """Return the latest stable or RC patch version for a runtime minor."""
    prefix = f'{runtime_minor}.'
    for prerelease in (False, True):
        versions = [
            release['tag_name'].removeprefix('v')
            for release in releases
            if release.get('prerelease') == prerelease
            and release['tag_name'].removeprefix('v').startswith(prefix)
        ]
        if versions:
            return sorted(versions, key=version_key)[-1]
    return None


def build_matrix(
    sdk_version: str,
    releases: list[dict[str, Any]],
    python_versions: tuple[str, ...] = DEFAULT_PYTHON_VERSIONS,
) -> dict[str, list[dict[str, str]]]:
    """Build the GitHub Actions strategy matrix for compatibility testing."""
    major, minor = parse_sdk_version(sdk_version)
    runtime_minors = runtime_minors_from_sdk(major, minor)
    matrix_include: list[dict[str, str]] = []

    for runtime_minor in runtime_minors:
        runtime_version = latest_patch_for_minor(releases, runtime_minor)
        if runtime_version is None:
            print(f'Warning: no Dapr runtime release found for {runtime_minor}, skipping')
            continue
        for python_version in python_versions:
            matrix_include.append(
                {
                    'python_ver': python_version,
                    'runtime_version': runtime_version,
                }
            )

    if not matrix_include:
        raise ValueError('No Dapr runtime releases found for compatibility matrix')

    return {'include': matrix_include}


def fetch_dapr_releases(
    github_token: str | None, timeout_seconds: float = 30.0
) -> list[dict[str, Any]]:
    """Fetch release metadata from the dapr/dapr GitHub repository."""
    headers: dict[str, str] = {}
    if github_token:
        headers['Authorization'] = f'Bearer {github_token}'

    request = urllib.request.Request(DAPR_RELEASES_URL, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.load(response)

    if not isinstance(payload, list):
        raise ValueError('Unexpected GitHub API response for dapr/dapr releases')

    return payload


def read_sdk_version(version_file: Path) -> str:
    """Read and strip the SDK version from VERSION."""
    return version_file.read_text(encoding='utf-8').strip()


def write_github_output(
    matrix: dict[str, list[dict[str, str]]], output_key: str = MATRIX_OUTPUT_KEY
) -> None:
    """Append matrix JSON to the GitHub Actions output file."""
    output_path = os.environ.get(GITHUB_OUTPUT_ENV)
    if not output_path:
        return

    with open(output_path, 'a', encoding='utf-8') as output_file:
        output_file.write(f'{output_key}={json.dumps(matrix)}\n')


def main(argv: list[str] | None = None) -> int:
    """Compute the compatibility matrix and print or write CI outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--version-file',
        type=Path,
        default=DEFAULT_VERSION_FILE,
        help='Path to the SDK VERSION file (default: VERSION)',
    )
    parser.add_argument(
        '--version',
        help='SDK version string (overrides --version-file)',
    )
    args = parser.parse_args(argv)

    sdk_version = args.version if args.version else read_sdk_version(args.version_file)
    github_token = os.environ.get(GITHUB_TOKEN_ENV)

    try:
        releases = fetch_dapr_releases(github_token)
    except urllib.error.URLError as err:
        print(f'Failed to fetch Dapr releases: {err}', file=sys.stderr)
        return 1

    try:
        matrix = build_matrix(sdk_version, releases)
    except ValueError as err:
        print(str(err), file=sys.stderr)
        return 1

    major, minor = parse_sdk_version(sdk_version)
    runtime_minors = runtime_minors_from_sdk(major, minor)
    print(f'SDK version: {sdk_version}')
    print(f'Runtime minors: {runtime_minors}')
    print(f'Matrix ({len(matrix["include"])} jobs): {json.dumps(matrix)}')

    write_github_output(matrix)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
