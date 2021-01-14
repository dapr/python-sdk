import json
import time

from dapr.clients import DaprClient

from opencensus.trace.tracer import Tracer
from opencensus.trace import time_event as time_event_module
from opencensus.ext.zipkin.trace_exporter import ZipkinExporter
from opencensus.trace.samplers import AlwaysOnSampler

ze = ZipkinExporter(
    service_name="python-example",
    host_name='localhost',
    port=9411,
    endpoint='/api/v2/spans')

tracer = Tracer(exporter=ze, sampler=AlwaysOnSampler())

with tracer.span(name="main") as span:
    with DaprClient(tracer=tracer) as d:

        num_messages = 2

        for i in range(num_messages):
            # Create a typed message with content type and body
            resp = d.invoke_method(
                'invoke-receiver',
                'say',
                data=json.dumps({
                    'id': i,
                    'message': 'hello world'
                    }),
            )
            # Print the response
            print(resp.content_type, flush=True)
            print(resp.text(), flush=True)

            resp = d.invoke_method('invoke-receiver', 'sleep', data='')
            # Print the response
            print(resp.content_type, flush=True)
            print(resp.text(), flush=True)
