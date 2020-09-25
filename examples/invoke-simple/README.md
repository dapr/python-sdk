# Example - Invoke

This example utilizes a receiver and a caller for the OnInvoke / Invoke functionality. It will create a gRPC server and bind the OnInvoke method, which gets called after a client sends a direct method invocation.

> **Note:** Make sure to use the latest proto bindings

## Running in self-host mode

To run this example, the following code can be utilized:

```bash
# 1. Start Receiver (expose gRPC server receiver on port 50051)
dapr run --app-id invoke-receiver --app-protocol grpc --app-port 50051 python3 invoke-receiver.py

# 2. Start Caller
dapr run --app-id invoke-caller --app-protocol grpc python3 invoke-caller.py
```

## Running in kubernetes mode

1. Build docker image

```
docker build -t [your registry]/invokesimple:latest .
```

2. Push docker image

```
docker push [your registry]/invokesimple:latest
```

3. Edit image name to `[your registry]/invokesimple:latest` in deploy/*.yaml

4. Deploy applications

```
cd deploy
kubectl apply -f .
```
