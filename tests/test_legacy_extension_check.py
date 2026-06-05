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
"""

# TODO: remove in 1.20 with the detection in dapr/__init__.py it tests.

import importlib.metadata
import tempfile
import unittest
import warnings
from pathlib import Path
from typing import Iterable
from unittest import mock

import dapr as dapr_pkg


class _FakeDist:
    """Stand-in for importlib.metadata.Distribution used by the detectors."""

    def __init__(self, version: str, files: Iterable[str] | None) -> None:
        self.version = version
        self._files = None if files is None else [Path(p) for p in files]

    @property
    def files(self) -> list[Path] | None:
        return self._files


def _distribution_factory(installed: dict[str, _FakeDist]):
    def _factory(name: str) -> _FakeDist:
        try:
            return installed[name]
        except KeyError as exc:
            raise importlib.metadata.PackageNotFoundError(name) from exc

    return _factory


class TestDetectLegacyExtensionDists(unittest.TestCase):
    def test_returns_empty_when_no_legacy_installed(self):
        with mock.patch.object(
            dapr_pkg.importlib.metadata, 'distribution', _distribution_factory({})
        ):
            self.assertEqual(dapr_pkg._detect_legacy_extension_dists(), [])

    def test_detects_legacy_dist_with_bundled_files(self):
        installed = {
            'dapr-ext-grpc': _FakeDist(
                version='1.18.0',
                files=['dapr/ext/grpc/__init__.py', 'dapr/ext/grpc/app.py'],
            ),
        }
        with mock.patch.object(
            dapr_pkg.importlib.metadata, 'distribution', _distribution_factory(installed)
        ):
            result = dapr_pkg._detect_legacy_extension_dists()
        self.assertEqual(result, ['dapr-ext-grpc==1.18.0'])

    def test_ignores_dist_that_does_not_own_bundled_path(self):
        # Modern flask-dapr-style stub dist that no longer ships dapr/ext/* files.
        installed = {
            'dapr-ext-grpc': _FakeDist(
                version='2.0.0',
                files=['some/other/path.py'],
            ),
        }
        with mock.patch.object(
            dapr_pkg.importlib.metadata, 'distribution', _distribution_factory(installed)
        ):
            self.assertEqual(dapr_pkg._detect_legacy_extension_dists(), [])

    def test_flags_install_when_record_is_missing(self):
        installed = {
            'flask-dapr': _FakeDist(version='1.17.0', files=None),
        }
        with mock.patch.object(
            dapr_pkg.importlib.metadata, 'distribution', _distribution_factory(installed)
        ):
            self.assertEqual(dapr_pkg._detect_legacy_extension_dists(), ['flask-dapr==1.17.0'])

    def test_swallows_unexpected_exceptions(self):
        def _broken(_name: str):
            raise RuntimeError('metadata backend exploded')

        with mock.patch.object(dapr_pkg.importlib.metadata, 'distribution', _broken):
            self.assertEqual(dapr_pkg._detect_legacy_extension_dists(), [])


class TestDetectMissingBundledFiles(unittest.TestCase):
    def _materialize_layout(self, tmp_path: Path, present: set[str]) -> Path:
        dapr_root = tmp_path / 'dapr'
        dapr_root.mkdir()
        (dapr_root / '__init__.py').write_text('')
        for prefix in dapr_pkg._LEGACY_DISTS_WITH_BUNDLED_PATHS.values():
            if prefix not in present:
                continue
            if prefix.startswith('dapr/'):
                target = dapr_root / prefix[len('dapr/') :] / '__init__.py'
            else:
                target = tmp_path / prefix / '__init__.py'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('')
        return dapr_root

    def test_returns_empty_when_all_paths_present(self):
        all_prefixes = set(dapr_pkg._LEGACY_DISTS_WITH_BUNDLED_PATHS.values())
        with tempfile.TemporaryDirectory() as tmp:
            dapr_root = self._materialize_layout(Path(tmp), all_prefixes)
            with mock.patch.object(dapr_pkg, '__file__', str(dapr_root / '__init__.py')):
                self.assertEqual(dapr_pkg._detect_missing_bundled_files(), [])

    def test_reports_missing_bundled_paths(self):
        present = {'dapr/ext/grpc', 'dapr/ext/workflow'}
        with tempfile.TemporaryDirectory() as tmp:
            dapr_root = self._materialize_layout(Path(tmp), present)
            with mock.patch.object(dapr_pkg, '__file__', str(dapr_root / '__init__.py')):
                missing = set(dapr_pkg._detect_missing_bundled_files())

        expected = set(dapr_pkg._LEGACY_DISTS_WITH_BUNDLED_PATHS.values()) - present
        self.assertEqual(missing, expected)

    def test_bails_out_when_dapr_root_not_a_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            phantom_init = Path(tmp) / 'not-a-dir' / '__init__.py'
            with mock.patch.object(dapr_pkg, '__file__', str(phantom_init)):
                self.assertEqual(dapr_pkg._detect_missing_bundled_files(), [])


class TestCheckForLegacyExtensionIssues(unittest.TestCase):
    def test_respects_skip_env_var(self):
        with mock.patch.dict('os.environ', {'DAPR_SKIP_LEGACY_CHECK': '1'}, clear=False):
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter('always')
                with mock.patch.object(
                    dapr_pkg, '_detect_legacy_extension_dists', return_value=['dapr-ext-grpc==1.0']
                ):
                    dapr_pkg._check_for_legacy_extension_issues()
        self.assertEqual(captured, [])

    def test_warns_for_legacy_installs_and_skips_filesystem_check(self):
        with mock.patch.dict('os.environ', {}, clear=False):
            with mock.patch.object(
                dapr_pkg, '_detect_legacy_extension_dists', return_value=['dapr-ext-grpc==1.0.0']
            ):
                with mock.patch.object(dapr_pkg, '_detect_missing_bundled_files') as missing_probe:
                    with warnings.catch_warnings(record=True) as captured:
                        warnings.simplefilter('always')
                        dapr_pkg._check_for_legacy_extension_issues()
        missing_probe.assert_not_called()
        self.assertEqual(len(captured), 1)
        warning = captured[0]
        self.assertIs(warning.category, FutureWarning)
        self.assertIn('dapr-ext-grpc==1.0.0', str(warning.message))
        self.assertIn('pip uninstall', str(warning.message))

    def test_warns_for_missing_bundled_paths(self):
        with mock.patch.dict('os.environ', {}, clear=False):
            with mock.patch.object(dapr_pkg, '_detect_legacy_extension_dists', return_value=[]):
                with mock.patch.object(
                    dapr_pkg,
                    '_detect_missing_bundled_files',
                    return_value=['dapr/ext/grpc'],
                ):
                    with warnings.catch_warnings(record=True) as captured:
                        warnings.simplefilter('always')
                        dapr_pkg._check_for_legacy_extension_issues()
        self.assertEqual(len(captured), 1)
        self.assertIs(captured[0].category, FutureWarning)
        self.assertIn('dapr/ext/grpc', str(captured[0].message))
        self.assertIn('--force-reinstall', str(captured[0].message))

    def test_silent_when_environment_is_clean(self):
        with mock.patch.dict('os.environ', {}, clear=False):
            with mock.patch.object(dapr_pkg, '_detect_legacy_extension_dists', return_value=[]):
                with mock.patch.object(dapr_pkg, '_detect_missing_bundled_files', return_value=[]):
                    with warnings.catch_warnings(record=True) as captured:
                        warnings.simplefilter('always')
                        dapr_pkg._check_for_legacy_extension_issues()
        self.assertEqual(captured, [])


class TestEmitLegacyWarning(unittest.TestCase):
    def test_falls_back_to_stderr_when_warning_escalated(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error', FutureWarning)
            with mock.patch('sys.stderr') as stderr_mock:
                dapr_pkg._emit_legacy_warning('legacy detected')
        stderr_mock.write.assert_called()
        written = ''.join(call.args[0] for call in stderr_mock.write.call_args_list)
        self.assertIn('legacy detected', written)


if __name__ == '__main__':
    unittest.main()
