# Distributed Tracing Sample

In this sample, we'll run two Python applications: a service application, which exposes two methods, and a client application which will invoke the methods from the service using Dapr. The code is instrumented with [OpenCensus SDK for Python](https://opencensus.io/guides/grpc/python/).
This sample includes:

* invoke-receiver (Exposes the methods to be remotely accessed)
* invoke-caller (Invokes the exposed methods)

Also consider [getting started with observability in Dapr](https://github.com/dapr/quickstarts/tree/master/observability).
 
## Remote invocation using the Python-SDK

This sample uses the Client provided in Dapr's Python SDK invoking a remote method and Zipkin to collect and display tracing data. 

## Pre-requisites

* [Dapr and Dapr CLI](https://github.com/dapr/docs/blob/master/getting-started/environment-setup.md#environment-setup).
* [Python 3](https://www.python.org/downloads/).

### Checking out the code

Clone this repository:

```sh
git clone https://github.com/dapr/python-sdk.git
cd python-sdk
```

Then get into the examples directory:

```sh
cd examples/w3c-tracing
```

Install dependencies:

```sh
pip3 install -r requirements.txt
```

### Verify Zipkin is running

Run `docker ps` to see if the container `dapr_zipkin` is running locally: 

```bash
CONTAINER ID        IMAGE                  COMMAND                  CREATED             STATUS              PORTS                              NAMES
24d043379da2        daprio/dapr            "./placement"            2 days ago          Up 32 hours         0.0.0.0:6050->50005/tcp            dapr_placement
5779a0268159        openzipkin/zipkin      "/busybox/sh run.sh"     2 days ago          Up 32 hours         9410/tcp, 0.0.0.0:9411->9411/tcp   dapr_zipkin
317fef6a8297        redis                  "docker-entrypoint.s…"   2 days ago          Up 32 hours         0.0.0.0:6379->6379/tcp             dapr_redis
```

If Zipkin is not working, [install the newest version of Dapr Cli and initialize it](https://github.com/dapr/cli#install-dapr-on-your-local-machine-self-hosted).

### Running the Demo service sample

The Demo service application exposes two methods that can be remotely invoked. In this example, the service code has two parts:

In the `invoke-receiver.py` file, you will find the OpenCensus tracing and exporter initialization in addition to two methods: `say` and `sleep`. The instrumentation for the service happens automatically via the `OpenCensusServerInterceptor` class.
```python
tracer_interceptor = server_interceptor.OpenCensusServerInterceptor(AlwaysOnSampler())
app = App(
    thread_pool=futures.ThreadPoolExecutor(max_workers=10),
    interceptors=(tracer_interceptor,))
```


The `say` method prints the incoming payload and metadata in console. See the code snippet below:

```python
@app.method(name='say')
def say(request: InvokeServiceRequest) -> InvokeServiceResponse:
    tracer = Tracer(sampler=AlwaysOnSampler())
    with tracer.span(name='say') as span:
        data = request.text()
        span.add_annotation('Request length', len=len(data))
        print(request.metadata, flush=True)
        print(request.text(), flush=True)

        return InvokeServiceResponse(b'SAY', "text/plain; charset=UTF-8")
```

The `sleep` methods simply waits for two seconds to simulate a slow operation.
```python
@app.method(name='sleep')
def sleep(request: InvokeServiceRequest) -> InvokeServiceResponse:
    tracer = Tracer(sampler=AlwaysOnSampler())
    with tracer.span(name='sleep') as _:
        time.sleep(2)
        print(request.metadata, flush=True)
        print(request.text(), flush=True)

        return InvokeServiceResponse(b'SLEEP', "text/plain; charset=UTF-8")
```

Use the follow command to execute the service:

```sh
dapr run --app-id invoke-receiver --app-protocol grpc --app-port 50051 python3 invoke-receiver.py
```

Once running, the service is now ready to be invoked by Dapr.


### Running the InvokeClient sample

This sample code uses the Dapr SDK for invoking two remote methods (`say` and `sleep`). Again, it is instrumented with OpenCensus with Zipkin exporter. See the code snippet below:

```python
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
            resp = d.invoke_service(
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

            resp = d.invoke_service('invoke-receiver', 'sleep', data='')
            # Print the response
            print(resp.content_type, flush=True)
            print(resp.text(), flush=True)
```

The class knows the app id for the remote application. It uses `invoke_service` method to invoke API calls on the service endpoint. Instrumentation happens automatically in `Dapr` client via the `tracer` argument.
 
Execute the follow script in order to run the caller example, it will make call each method twice:
```sh
dapr run --app-id invoke-caller --app-protocol grpc python3 invoke-caller.py
```
Once running, the output should display the messages sent from invoker in the service output as follows:

![exposeroutput](https://raw.githubusercontent.com/dapr/python-sdk/master/examples/w3c-tracing/img/service.png)

Method have been remotely invoked and displaying the remote messages.

Now, open Zipkin on [http://localhost:9411/zipkin](http://localhost:9411/zipkin). You should see a screen like the one below:

![zipking-landing](https://raw.githubusercontent.com/dapr/python-sdk/master/examples/w3c-tracing/img/zipkin-landing.png)

Click on the search icon to see the latest query results. You should see a tracing diagram similar to the one below:

![zipking-landing](https://raw.githubusercontent.com/dapr/python-sdk/master/examples/w3c-tracing/img/zipkin-result.png)

Once you click on the tracing event, you will see the details of the call stack starting in the client and then showing the service API calls right below.

![zipking-details](https://raw.githubusercontent.com/dapr/python-sdk/master/examples/w3c-tracing/img/zipkin-details.png)
