import time

from concurrent import futures

from dapr.ext.grpc import App, InvokeMethodRequest, InvokeMethodResponse

from opencensus.trace.samplers import AlwaysOnSampler
from opencensus.trace.tracer import Tracer
from opencensus.ext.grpc import server_interceptor
from opencensus.trace.samplers import AlwaysOnSampler

tracer_interceptor = server_interceptor.OpenCensusServerInterceptor(AlwaysOnSampler())
app = App(
    thread_pool=futures.ThreadPoolExecutor(max_workers=10),
    interceptors=(tracer_interceptor,))

@app.method(name='say')
def say(request: InvokeMethodRequest) -> InvokeMethodResponse:
    tracer = Tracer(sampler=AlwaysOnSampler())
    with tracer.span(name='say') as span:
        data = request.text()
        span.add_annotation('Request length', len=len(data))
        print(request.metadata, flush=True)
        print(request.text(), flush=True)

        return InvokeMethodResponse(b'SAY', "text/plain; charset=UTF-8")

@app.method(name='sleep')
def sleep(request: InvokeMethodRequest) -> InvokeMethodResponse:
    tracer = Tracer(sampler=AlwaysOnSampler())
    with tracer.span(name='sleep') as _:
        time.sleep(2)
        print(request.metadata, flush=True)
        print(request.text(), flush=True)

        return InvokeMethodResponse(b'SLEEP', "text/plain; charset=UTF-8")


app.run(50051)
