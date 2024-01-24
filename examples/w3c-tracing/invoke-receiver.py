import json
import time
import typing
from concurrent import futures

from opentelemetry import trace
from opentelemetry.exporter.zipkin.json import ZipkinExporter
from opentelemetry.instrumentation.grpc import GrpcInstrumentorServer, filters
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from dapr.clients import DaprClient
from dapr.ext.grpc import App, InvokeMethodRequest, InvokeMethodResponse

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

# automatically intercept incoming tracing headers and propagate them to the current context
grpc_server_instrumentor = GrpcInstrumentorServer()
grpc_server_instrumentor.instrument()


app = App(thread_pool=futures.ThreadPoolExecutor(max_workers=10))


@app.method(name='saytrace')
def saytrace(request: InvokeMethodRequest) -> InvokeMethodResponse:
    with tracer.start_as_current_span(name='say') as span:
        data = request.text()
        span.add_event(name='log', attributes={'Request length': len(data)})
        print(request.metadata, flush=True)
        print(request.text(), flush=True)

        resp = {'receivedtraceid': span.get_span_context().trace_id, 'method': 'SAY'}

        return InvokeMethodResponse(json.dumps(resp), 'application/json; charset=UTF-8')


@app.method(name='sleep')
def sleep(request: InvokeMethodRequest) -> InvokeMethodResponse:
    with tracer.start_as_current_span(name='sleep'):
        time.sleep(2)
        print(request.metadata, flush=True)
        print(request.text(), flush=True)

        return InvokeMethodResponse(b'SLEEP', 'text/plain; charset=UTF-8')


# This method is used to forward the request to another service
# this is used to test the tracing propagation
@app.method(name='forward')
def forward(request: InvokeMethodRequest) -> InvokeMethodResponse:
    with tracer.start_as_current_span(name='forward'):
        print(request.metadata, flush=True)
        print(request.text(), flush=True)

        # this helper method can be used to inject the tracing headers into the request
        def trace_injector() -> typing.Dict[str, str]:
            headers: typing.Dict[str, str] = {}
            TraceContextTextMapPropagator().inject(carrier=headers)
            return headers

        # service invocation uses HTTP, so we need to inject the tracing headers into the request
        with DaprClient(headers_callback=trace_injector) as d:
            resp = d.invoke_method(
                'invoke-receiver',
                'saytrace',
                data=request.text().encode('utf-8'),
            )

        return InvokeMethodResponse(json.dumps(resp.json()), 'application/json; charset=UTF-8')


app.run(3001)
