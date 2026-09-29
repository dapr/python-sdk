import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

import httpx

from dapr.credentials.oauth2 import GRANT_TYPE_TOKEN_EXCHANGE, RFC8693TokenExchangeProvider
from dapr.credentials.sources import CallableAttestationSource


def _json_response(status_code: int, body: dict) -> httpx.Response:
    return httpx.Response(status_code, json=body)


class RFC8693TokenExchangeProviderTests(unittest.TestCase):
    def _make_provider(self, handler, **kwargs) -> RFC8693TokenExchangeProvider:
        transport = httpx.MockTransport(handler)
        return RFC8693TokenExchangeProvider(
            token_url='https://idp.example.com/token',
            attestation=CallableAttestationSource(lambda: 'subject-token'),
            transport=transport,
            async_transport=transport,
            **kwargs,
        )

    def test_fetch_returns_bearer_credential_with_expiry(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response(200, {'access_token': 'issued-token', 'expires_in': 300})

        provider = self._make_provider(handler)
        before = datetime.now(timezone.utc)
        credential = provider.fetch()

        self.assertEqual(credential.token, 'issued-token')
        self.assertIsNotNone(credential.expires_at)
        self.assertGreater(credential.expires_at, before + timedelta(seconds=299))
        self.assertLess(credential.expires_at, before + timedelta(seconds=310))

    def test_fetch_without_expires_in_is_long_lived(self):
        provider = self._make_provider(
            lambda request: _json_response(200, {'access_token': 'token'})
        )
        credential = provider.fetch()
        self.assertIsNone(credential.expires_at)
        self.assertFalse(credential.is_expired())

    def test_fetch_sends_standard_rfc8693_form(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured['form'] = parse_qs(request.content.decode('utf-8'))
            return _json_response(200, {'access_token': 't'})

        provider = self._make_provider(handler, audience='my-aud', scope='my-scope')
        provider.fetch()

        form = captured['form']
        self.assertEqual(form['grant_type'], [GRANT_TYPE_TOKEN_EXCHANGE])
        self.assertEqual(form['subject_token'], ['subject-token'])
        self.assertEqual(form['audience'], ['my-aud'])
        self.assertEqual(form['scope'], ['my-scope'])

    def test_fetch_raises_on_missing_access_token(self):
        provider = self._make_provider(lambda request: _json_response(200, {}))
        with self.assertRaises(ValueError):
            provider.fetch()

    def test_fetch_raises_on_http_error_status_with_the_error_body(self):
        provider = self._make_provider(
            lambda request: httpx.Response(401, json={'error': 'invalid_client'})
        )
        with self.assertRaises(httpx.HTTPStatusError) as raised:
            provider.fetch()
        self.assertIn('401', str(raised.exception))
        self.assertIn('invalid_client', str(raised.exception))

    def test_fetch_truncates_a_long_error_body(self):
        provider = self._make_provider(lambda request: httpx.Response(500, text='x' * 10_000))
        with self.assertRaises(httpx.HTTPStatusError) as raised:
            provider.fetch()
        self.assertLess(len(str(raised.exception)), 1_000)

    def test_fetch_omits_audience_and_scope_when_unset(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured['form'] = parse_qs(request.content.decode('utf-8'))
            return _json_response(200, {'access_token': 't'})

        self._make_provider(handler).fetch()

        self.assertNotIn('audience', captured['form'])
        self.assertNotIn('scope', captured['form'])

    def test_fetch_rejects_a_non_numeric_expires_in(self):
        for expires_in in ('300', True, [300]):
            with self.subTest(expires_in=expires_in):
                provider = self._make_provider(
                    lambda request: _json_response(
                        200, {'access_token': 't', 'expires_in': expires_in}
                    )
                )
                with self.assertRaises(ValueError):
                    provider.fetch()


class RFC8693TokenExchangeProviderAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_async_returns_bearer_credential(self):
        transport = httpx.MockTransport(
            lambda request: _json_response(200, {'access_token': 'async-token', 'expires_in': 60})
        )
        provider = RFC8693TokenExchangeProvider(
            token_url='https://idp.example.com/token',
            attestation=CallableAttestationSource(lambda: 'subject-token'),
            async_transport=transport,
        )
        credential = await provider.fetch_async()
        self.assertEqual(credential.token, 'async-token')

    async def test_fetch_async_raises_on_http_error_status(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(403, text='denied'))
        provider = RFC8693TokenExchangeProvider(
            token_url='https://idp.example.com/token',
            attestation=CallableAttestationSource(lambda: 'subject-token'),
            async_transport=transport,
        )
        with self.assertRaises(httpx.HTTPStatusError):
            await provider.fetch_async()


if __name__ == '__main__':
    unittest.main()
