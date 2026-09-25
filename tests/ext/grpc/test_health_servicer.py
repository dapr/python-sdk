import unittest
from unittest.mock import MagicMock

from dapr.ext.grpc._health_servicer import _HealthCheckServicer


class OnInvokeTests(unittest.TestCase):
    def setUp(self):
        self._health_servicer = _HealthCheckServicer()

    def test_healthcheck_cb_called(self):
        health_cb = MagicMock()
        self._health_servicer.register_health_check(health_cb)
        self._health_servicer.HealthCheck(None, MagicMock())
        health_cb.assert_called_once()

    def test_no_healthcheck_cb(self):
        with self.assertRaises(NotImplementedError) as exception_context:
            self._health_servicer.HealthCheck(None, MagicMock())
        self.assertIn('Method not implemented!', exception_context.exception.args[0])
