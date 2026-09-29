import unittest

from dapr.credentials._http import get_bearer_header
from dapr.credentials.manager import AsyncCredentialManager
from tests.credentials._fakes import FakeProvider


class GetBearerHeaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_the_token_under_the_given_header_name(self):
        manager = AsyncCredentialManager(FakeProvider())
        headers = await get_bearer_header(manager, header_name='authorization')
        self.assertEqual(headers, {'authorization': 'token-1'})

    async def test_defaults_to_the_dapr_api_token_header(self):
        headers = await get_bearer_header(AsyncCredentialManager(FakeProvider()))
        self.assertEqual(list(headers), ['dapr-api-token'])


if __name__ == '__main__':
    unittest.main()
