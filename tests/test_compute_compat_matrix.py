import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent.parent / 'tools' / 'compute_compat_matrix.py'
_spec = spec_from_file_location('compute_compat_matrix', _MODULE_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f'Cannot load compute_compat_matrix from {_MODULE_PATH}')
compute_compat_matrix = module_from_spec(_spec)
_spec.loader.exec_module(compute_compat_matrix)

parse_sdk_version = compute_compat_matrix.parse_sdk_version
runtime_minors_from_sdk = compute_compat_matrix.runtime_minors_from_sdk
version_key = compute_compat_matrix.version_key
latest_patch_for_minor = compute_compat_matrix.latest_patch_for_minor
build_matrix = compute_compat_matrix.build_matrix

SAMPLE_RELEASES = [
    {'tag_name': 'v1.18.0', 'prerelease': False},
    {'tag_name': 'v1.18.0-rc.5', 'prerelease': True},
    {'tag_name': 'v1.18.0-rc.1', 'prerelease': True},
    {'tag_name': 'v1.17.9', 'prerelease': False},
    {'tag_name': 'v1.17.0', 'prerelease': False},
    {'tag_name': 'v1.16.14', 'prerelease': False},
]


class ParseSdkVersionTests(unittest.TestCase):
    def test_strips_dev_suffix(self) -> None:
        self.assertEqual(parse_sdk_version('1.19.0.dev'), (1, 19))

    def test_stable_version(self) -> None:
        self.assertEqual(parse_sdk_version('1.18.0'), (1, 18))


class RuntimeMinorsFromSdkTests(unittest.TestCase):
    def test_three_minors_from_main(self) -> None:
        self.assertEqual(runtime_minors_from_sdk(1, 19), ['1.19', '1.18', '1.17'])

    def test_three_minors_from_release_branch(self) -> None:
        self.assertEqual(runtime_minors_from_sdk(1, 16), ['1.16', '1.15', '1.14'])


class VersionKeyTests(unittest.TestCase):
    def test_rc_ordering(self) -> None:
        self.assertLess(version_key('1.18.0-rc.1'), version_key('1.18.0-rc.5'))

    def test_stable_ordering(self) -> None:
        self.assertLess(version_key('1.17.0'), version_key('1.17.9'))


class LatestPatchForMinorTests(unittest.TestCase):
    def test_prefers_stable_over_rc(self) -> None:
        patch = latest_patch_for_minor(SAMPLE_RELEASES, '1.18')
        self.assertEqual(patch, '1.18.0')

    def test_picks_latest_stable_patch(self) -> None:
        patch = latest_patch_for_minor(SAMPLE_RELEASES, '1.17')
        self.assertEqual(patch, '1.17.9')

    def test_falls_back_to_rc_when_no_stable(self) -> None:
        releases = [
            {'tag_name': 'v1.19.0-rc.2', 'prerelease': True},
            {'tag_name': 'v1.19.0-rc.5', 'prerelease': True},
        ]
        patch = latest_patch_for_minor(releases, '1.19')
        self.assertEqual(patch, '1.19.0-rc.5')

    def test_returns_none_when_missing(self) -> None:
        self.assertIsNone(latest_patch_for_minor(SAMPLE_RELEASES, '1.15'))


class BuildMatrixTests(unittest.TestCase):
    def test_builds_python_by_runtime_jobs(self) -> None:
        matrix = build_matrix('1.18.0', SAMPLE_RELEASES, python_versions=('3.10', '3.11'))

        self.assertEqual(len(matrix['include']), 6)
        self.assertEqual(
            matrix['include'][0],
            {'python_ver': '3.10', 'runtime_version': '1.18.0'},
        )

    def test_skips_unresolved_runtime_minor(self) -> None:
        matrix = build_matrix('1.19.0.dev', SAMPLE_RELEASES, python_versions=('3.10',))

        runtime_versions = {entry['runtime_version'] for entry in matrix['include']}
        self.assertEqual(runtime_versions, {'1.18.0', '1.17.9'})

    def test_raises_when_no_runtime_resolves(self) -> None:
        with self.assertRaises(ValueError):
            build_matrix('1.20.0.dev', [], python_versions=('3.10',))


if __name__ == '__main__':
    unittest.main()
