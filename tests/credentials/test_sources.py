import tempfile
import unittest
from pathlib import Path

from dapr.credentials.sources import (
    DEFAULT_KUBERNETES_TOKEN_PATH,
    CallableAttestationSource,
    FileAttestationSource,
    kubernetes_service_account_source,
)


class CallableAttestationSourceTests(unittest.TestCase):
    def test_invokes_the_callable_on_every_call(self):
        tokens = iter(['token-1', 'token-2'])
        source = CallableAttestationSource(lambda: next(tokens))
        self.assertEqual(source.get(), 'token-1')
        self.assertEqual(source.get(), 'token-2')


class FileAttestationSourceTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)
        self.path = Path(self._tmp_dir.name) / 'token'

    def test_reads_and_strips_the_file(self):
        self.path.write_text('  a-token  \n')
        self.assertEqual(FileAttestationSource(self.path).get(), 'a-token')

    def test_rereads_the_file_on_every_call_to_pick_up_rotation(self):
        source = FileAttestationSource(self.path)
        self.path.write_text('first')
        self.assertEqual(source.get(), 'first')
        self.path.write_text('second')
        self.assertEqual(source.get(), 'second')


class KubernetesServiceAccountSourceTests(unittest.TestCase):
    def test_reads_the_given_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / 'token'
            path.write_text('projected-token')
            self.assertEqual(kubernetes_service_account_source(path).get(), 'projected-token')

    def test_defaults_to_the_dapr_projected_token_path(self):
        self.assertEqual(
            DEFAULT_KUBERNETES_TOKEN_PATH,
            Path('/var/run/secrets/dapr.io/serviceaccount/token'),
        )
        self.assertIsInstance(kubernetes_service_account_source(), FileAttestationSource)


if __name__ == '__main__':
    unittest.main()
