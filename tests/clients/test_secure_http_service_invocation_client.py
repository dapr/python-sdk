# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
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
import ssl
import typing
from asyncio import TimeoutError

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from dapr.clients import DaprClient
from dapr.clients.health import DaprHealth
from dapr.clients.http.client import DaprHttpClient
from dapr.conf import settings
from dapr.proto import common_v1


from .certs import replacement_get_health_context
from .fake_http_server import FakeHttpServer
from .test_http_service_invocation_client import DaprInvocationHttpClientTests


def replacement_get_client_ssl_context(a):
    """
    This method is used (overwritten) from tests
    to return context for self-signed certificates
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    return context


DaprHttpClient.get_ssl_context = replacement_get_client_ssl_context
DaprHealth.get_ssl_context = replacement_get_health_context


class DaprSecureInvocationHttpClientTests(DaprInvocationHttpClientTests):
    def setUp(self):
        self.server = FakeHttpServer(port=4443)
        self.server_port = self.server.get_port()
        self.server.start_secure()
        settings.DAPR_HTTP_PORT = self.server_port
        settings.DAPR_API_METHOD_INVOCATION_PROTOCOL = 'http'
        settings.DAPR_HTTP_ENDPOINT = 'https://127.0.0.1:{}'.format(self.server_port)
        self.client = DaprClient()
        self.app_id = 'fakeapp'
        self.method_name = 'fakemethod'
        self.invoke_url = f'/v1.0/invoke/{self.app_id}/method/{self.method_name}'

    def tearDown(self):
        self.server.shutdown_server()
        settings.DAPR_API_TOKEN = None
        settings.DAPR_API_METHOD_INVOCATION_PROTOCOL = 'http'

    def test_global_timeout_setting_is_honored(self):
        previous_timeout = settings.DAPR_HTTP_TIMEOUT_SECONDS
        settings.DAPR_HTTP_TIMEOUT_SECONDS = 1
        new_client = DaprClient(f'https://localhost:{self.server_port}')
        self.server.set_server_delay(1.5)
        with self.assertRaises(TimeoutError):
            new_client.invoke_method(self.app_id, self.method_name, '')

        settings.DAPR_HTTP_TIMEOUT_SECONDS = previous_timeout

    def test_invoke_method_with_tracer(self):
        # Create a tracer provider
        tracer_provider = TracerProvider(sampler=ALWAYS_ON)

        # Create a span processor
        span_processor = BatchSpanProcessor(ConsoleSpanExporter())

        # Add the span processor to the tracer provider
        tracer_provider.add_span_processor(span_processor)

        # Set the tracer provider
        trace.set_tracer_provider(tracer_provider)

        # Get the tracer
        tracer = trace.get_tracer(__name__)

        def trace_injector() -> typing.Dict[str, str]:
            headers: typing.Dict[str, str] = {}
            TraceContextTextMapPropagator().inject(carrier=headers)
            return headers

        self.client = DaprClient(
            f'https://localhost:{self.server_port}',
            headers_callback=trace_injector,
        )
        self.server.set_response(b'FOO')

        with tracer.start_as_current_span(name='test'):
            req = common_v1.StateItem(key='test')
            resp = self.client.invoke_method(
                self.app_id,
                self.method_name,
                http_verb='PUT',
                data=req,
            )

        request_headers: typing.Dict[str, str] = self.server.get_request_headers()

        self.assertIn('Traceparent', request_headers)
        self.assertEqual(b'FOO', resp.data)

    def test_timeout_exception_thrown_when_timeout_reached(self):
        new_client = DaprClient(f'https://localhost:{self.server_port}', http_timeout_seconds=1)
        self.server.set_server_delay(1.5)
        with self.assertRaises(TimeoutError):
            new_client.invoke_method(self.app_id, self.method_name, '')
