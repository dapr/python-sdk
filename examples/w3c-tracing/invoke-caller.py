import json
import typing

from opentelemetry import trace
from opentelemetry.exporter.zipkin.json import ZipkinExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from dapr.clients import DaprClient

# Create a tracer provider
tracer_provider = TracerProvider(sampler=ALWAYS_ON)

# Create a span processor
span_processor = BatchSpanProcessor(ZipkinExporter(endpoint='http://localhost:9411/api/v2/spans'))

# Add the span processor to the tracer provider
tracer_provider.add_span_processor(span_processor)

# Set the tracer provider
trace.set_tracer_provider(tracer_provider)

# Get the tracer
tracer = trace.get_tracer(__name__)


# this helper method can be used to inject the tracing headers into the request
def trace_injector() -> typing.Dict[str, str]:
    headers: typing.Dict[str, str] = {}
    TraceContextTextMapPropagator().inject(carrier=headers)
    return headers


with tracer.start_as_current_span(name='main') as span:
    with DaprClient(
        # service invocation uses HTTP, so we need to inject the tracing headers into the request
        headers_callback=lambda: trace_injector()
    ) as d:
        num_messages = 2

        for i in range(num_messages):
            # Create a typed message with content type and body
            resp = d.invoke_method(
                'invoke-receiver',
                'saytrace',
                data=json.dumps({'id': i, 'message': 'hello world'}),
            )
            # Print the response
            print(resp.content_type, flush=True)
            print(resp.json()['method'], flush=True)
            traceid = resp.json()['receivedtraceid']

            resp = d.invoke_method('invoke-receiver', 'sleep', data='')
            # Print the response
            print(resp.content_type, flush=True)
            print(resp.text(), flush=True)

            forwarded_resp = d.invoke_method('invoke-receiver', 'forward', data='')
            match_string = (
                'matches'
                if (forwarded_resp.json()['receivedtraceid'] == traceid)
                else 'does not match'
            )
            print(f'Trace ID {match_string} after forwarding', flush=True)
