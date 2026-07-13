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

Guards the coupling between checked-in gencode and the pyproject.toml floors.

The protoc bundled with grpcio-tools stamps every generated *_pb2.py with its
own protobuf version, which ValidateProtobufRuntimeVersion enforces as the
minimum runtime version when users import the SDK. Likewise every *_pb2_grpc.py
embeds GRPC_GENERATED_VERSION (the grpcio-tools version) as the minimum grpcio.
Regenerating protos with a newer grpcio-tools therefore silently raises the
real user-facing requirements. These tests fail any PR where the committed
gencode demands more than the floors pyproject.toml declares, so bumping a
floor is always a deliberate pyproject.toml change.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PROTOBUF_STAMP_PATTERN = re.compile(
    r'_runtime_version\.ValidateProtobufRuntimeVersion\(\s*'
    r'_runtime_version\.Domain\.PUBLIC,\s*(\d+),\s*(\d+),\s*(\d+)'
)
GRPC_STAMP_PATTERN = re.compile(r'GRPC_GENERATED_VERSION = \'(\d+)\.(\d+)\.(\d+)\'')


def parse_declared_floor(package_name: str) -> tuple[int, int, int]:
    """Extracts the `<package>>=X.Y.Z` floor from pyproject.toml dependencies.

    Parsed with a targeted regex instead of tomllib because the SDK still
    supports Python 3.10, which lacks tomllib.
    """
    pyproject_text = (REPO_ROOT / 'pyproject.toml').read_text(encoding='utf-8')
    floor_pattern = re.compile(rf'"{package_name}>=(\d+)\.(\d+)\.(\d+)')
    floor_matches = floor_pattern.findall(pyproject_text)
    if len(floor_matches) != 1:
        raise AssertionError(
            f'Expected exactly one "{package_name}>=X.Y.Z" constraint in pyproject.toml, '
            f'found {len(floor_matches)}'
        )
    major, minor, patch = floor_matches[0]
    return int(major), int(minor), int(patch)


def read_stamps(glob_pattern: str, stamp_pattern: re.Pattern) -> dict[Path, tuple[int, int, int]]:
    """Maps each generated file under dapr/ to its embedded minimum-version stamp."""
    stamps: dict[Path, tuple[int, int, int]] = {}
    for gencode_path in sorted((REPO_ROOT / 'dapr').rglob(glob_pattern)):
        stamp_match = stamp_pattern.search(gencode_path.read_text(encoding='utf-8'))
        if stamp_match is None:
            raise AssertionError(
                f'{gencode_path} has no recognizable version stamp; if the generated '
                f'format changed, update the patterns in this test'
            )
        major, minor, patch = stamp_match.groups()
        stamps[gencode_path] = (int(major), int(minor), int(patch))
    return stamps


class ProtoGencodeFloorTests(unittest.TestCase):
    def assert_stamps_within_floor(self, stamps: dict, floor: tuple, floor_package: str) -> None:
        self.assertGreater(len(stamps), 0, 'no generated files found; glob broken?')
        floor_display = '.'.join(str(part) for part in floor)
        violations = [
            f'{path.relative_to(REPO_ROOT)} requires {".".join(str(p) for p in stamp)}'
            for path, stamp in stamps.items()
            if stamp > floor
        ]
        self.assertEqual(
            violations,
            [],
            f'\nGenerated code demands a newer {floor_package} than the '
            f'"{floor_package}>={floor_display}" floor in pyproject.toml allows, so users on '
            f'the floor version would crash at import. Either bump the {floor_package} floor '
            f'(a deliberate user-facing requirement change) or regenerate with the '
            f'grpcio-tools release matching the floor.',
        )

    def test_protobuf_stamps_within_declared_floor(self):
        protobuf_floor = parse_declared_floor('protobuf')
        protobuf_stamps = read_stamps('*_pb2.py', PROTOBUF_STAMP_PATTERN)
        self.assert_stamps_within_floor(protobuf_stamps, protobuf_floor, 'protobuf')

    def test_grpc_stamps_within_declared_floor(self):
        grpcio_floor = parse_declared_floor('grpcio')
        grpc_stamps = read_stamps('*_pb2_grpc.py', GRPC_STAMP_PATTERN)
        self.assert_stamps_within_floor(grpc_stamps, grpcio_floor, 'grpcio')


if __name__ == '__main__':
    unittest.main()
