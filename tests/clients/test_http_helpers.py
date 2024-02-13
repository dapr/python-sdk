import unittest
from unittest.mock import patch

from dapr.conf import settings
from dapr.clients.http.helpers import get_api_url


class DaprHttpClientHelpersTests(unittest.TestCase):
    def test_get_api_url_default(self, dapr=None):
        self.assertEqual(
            'http://{}:{}/{}'.format(
                settings.DAPR_RUNTIME_HOST, settings.DAPR_HTTP_PORT, settings.DAPR_API_VERSION
            ),
            get_api_url(),
        )

    @patch.object(settings, 'DAPR_HTTP_ENDPOINT', 'https://domain1.com:5000')
    def test_get_api_url_endpoint_as_env_variable(self):
        self.assertEqual(
            'https://domain1.com:5000/{}'.format(settings.DAPR_API_VERSION),
            get_api_url(),
        )
