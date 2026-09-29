import unittest
from datetime import datetime, timedelta, timezone

from dapr.credentials.base import CredentialProvider, WorkloadCredential


class _Provider(CredentialProvider):
    def fetch(self) -> WorkloadCredential:
        return WorkloadCredential(token='fetched')


class WorkloadCredentialTests(unittest.TestCase):
    def test_rejects_an_empty_token(self):
        with self.assertRaises(ValueError):
            WorkloadCredential(token='')

    def test_expires_at_must_be_timezone_aware(self):
        with self.assertRaises(ValueError):
            WorkloadCredential(token='t', expires_at=datetime.now())

    def test_a_credential_without_expiry_never_expires(self):
        self.assertFalse(WorkloadCredential(token='t').is_expired())

    def test_expiry_boundary(self):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=10)
        credential = WorkloadCredential(token='t', expires_at=expires_at)
        self.assertFalse(credential.is_expired(now=expires_at - timedelta(seconds=1)))
        self.assertTrue(credential.is_expired(now=expires_at))
        self.assertTrue(credential.is_expired(now=expires_at + timedelta(seconds=1)))


class CredentialProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_async_defaults_to_fetch(self):
        credential = await _Provider().fetch_async()
        self.assertEqual(credential.token, 'fetched')


if __name__ == '__main__':
    unittest.main()
