import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dapr.conf import settings
from dapr.credentials._settings import resolve_default_credential_provider
from dapr.credentials.oauth2 import RFC8693TokenExchangeProvider

TOKEN_URL = 'https://idp.example.com/token'


class ResolveDefaultCredentialProviderTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)
        self.token_path = Path(self._tmp_dir.name) / 'token'
        self.token_path.write_text('subject-token')

    def test_returns_none_when_nothing_is_configured(self):
        self.assertIsNone(resolve_default_credential_provider())

    def test_builds_a_token_exchange_provider(self):
        with (
            patch.object(settings, 'DAPR_WORKLOAD_IDENTITY_TOKEN_URL', TOKEN_URL),
            patch.object(settings, 'DAPR_WORKLOAD_IDENTITY_TOKEN_FILE_PATH', str(self.token_path)),
        ):
            provider = resolve_default_credential_provider()

        self.assertIsInstance(provider, RFC8693TokenExchangeProvider)

    def test_rejects_a_partial_configuration(self):
        for setting, value in (
            ('DAPR_WORKLOAD_IDENTITY_TOKEN_URL', TOKEN_URL),
            ('DAPR_WORKLOAD_IDENTITY_TOKEN_FILE_PATH', str(self.token_path)),
        ):
            with self.subTest(setting=setting), patch.object(settings, setting, value):
                with self.assertRaises(ValueError):
                    resolve_default_credential_provider()

    def test_takes_precedence_over_the_api_token_with_a_warning(self):
        with (
            patch.object(settings, 'DAPR_WORKLOAD_IDENTITY_TOKEN_URL', TOKEN_URL),
            patch.object(settings, 'DAPR_WORKLOAD_IDENTITY_TOKEN_FILE_PATH', str(self.token_path)),
            patch.object(settings, 'DAPR_API_TOKEN', 'static-token'),
        ):
            with self.assertLogs('dapr.credentials._settings', level='WARNING') as logs:
                provider = resolve_default_credential_provider()

        self.assertIsInstance(provider, RFC8693TokenExchangeProvider)
        self.assertTrue(any('DAPR_API_TOKEN' in message for message in logs.output))


if __name__ == '__main__':
    unittest.main()
