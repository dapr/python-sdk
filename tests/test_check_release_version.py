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

Covers tools/check_release_version.py, the gate the release workflows run
before a tag is created and again before anything is published.
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / 'tools' / 'check_release_version.py'


def load_script() -> ModuleType:
    """Loads the script as a module; tools/ is not an importable package."""
    module_spec = importlib.util.spec_from_file_location('check_release_version', SCRIPT_PATH)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


crv = load_script()


class ReleaseVersionFormatTests(unittest.TestCase):
    def test_accepts_stable_and_rc_versions(self) -> None:
        for version in ('1.19.0', '1.19.0rc0', '1.19.0rc12', '1.18.3', '2.0.1rc1'):
            with self.subTest(version=version):
                crv.check_release_version(version)

    def test_rejects_dev_and_non_normalized_versions(self) -> None:
        for version in ('1.19.0.dev', '1.19.0-rc1', '1.19.0.rc1', '1.19', 'v1.19.0', ''):
            with self.subTest(version=version):
                with self.assertRaises(crv.ReleaseVersionError):
                    crv.check_release_version(version)


class ExpectedVersionTests(unittest.TestCase):
    def test_matching_version_passes_with_or_without_tag_prefix(self) -> None:
        crv.check_expected_version('1.19.0rc2', '1.19.0rc2')
        crv.check_expected_version('1.19.0rc2', 'v1.19.0rc2')

    def test_unbumped_version_fails(self) -> None:
        with self.assertRaisesRegex(crv.ReleaseVersionError, 'Bump VERSION'):
            crv.check_expected_version('1.19.0rc1', '1.19.0rc2')


class BranchTests(unittest.TestCase):
    def test_version_in_branch_series_passes(self) -> None:
        crv.check_branch('1.19.0rc2', 'release-1.19')
        crv.check_branch('1.19.1', 'refs/heads/release-1.19')

    def test_version_from_another_series_fails(self) -> None:
        with self.assertRaisesRegex(crv.ReleaseVersionError, 'release-1.19'):
            crv.check_branch('1.20.0rc0', 'release-1.19')

    def test_non_release_branch_fails(self) -> None:
        for branch in ('main', 'release-1', 'feature/release-1.19', 'release-1.19-hotfix'):
            with self.subTest(branch=branch):
                with self.assertRaises(crv.ReleaseVersionError):
                    crv.check_branch('1.19.0', branch)


class TagTests(unittest.TestCase):
    def test_matching_tag_passes(self) -> None:
        crv.check_tag('1.19.0rc2', 'v1.19.0rc2')
        crv.check_tag('1.19.0rc2', 'refs/tags/v1.19.0rc2')

    def test_tag_ahead_of_version_fails(self) -> None:
        with self.assertRaisesRegex(crv.ReleaseVersionError, 'Bump VERSION before tagging'):
            crv.check_tag('1.19.0rc1', 'v1.19.0rc2')


class UntaggedTests(unittest.TestCase):
    def test_new_version_passes(self) -> None:
        crv.check_untagged('1.19.0rc2', {'v1.19.0rc0', 'v1.19.0rc1'})

    def test_already_released_version_fails(self) -> None:
        with self.assertRaisesRegex(crv.ReleaseVersionError, 'already exists'):
            crv.check_untagged('1.19.0rc1', {'v1.19.0rc0', 'v1.19.0rc1'})


class MainTests(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.version_path = Path(temp_dir.name) / 'VERSION'
        self.version_path.write_text('1.19.0rc1\n', encoding='utf-8')

    def run_main(self, *args: str) -> int:
        exit_code: int = crv.main(['--version-file', str(self.version_path), *args])
        return exit_code

    def test_passes_when_every_check_holds(self) -> None:
        exit_code = self.run_main('--expected', '1.19.0rc1', '--branch', 'release-1.19')
        self.assertEqual(exit_code, 0)

    def test_fails_when_version_was_not_bumped(self) -> None:
        with self.assertLogs(crv.logger, level='ERROR') as captured_logs:
            exit_code = self.run_main('--expected', '1.19.0rc2', '--branch', 'release-1.19')
        self.assertEqual(exit_code, 1)
        self.assertIn('Bump VERSION', captured_logs.output[0])

    def test_fails_when_tag_does_not_match(self) -> None:
        with self.assertLogs(crv.logger, level='ERROR'):
            exit_code = self.run_main('--tag', 'v1.19.0rc2')
        self.assertEqual(exit_code, 1)


if __name__ == '__main__':
    unittest.main()
