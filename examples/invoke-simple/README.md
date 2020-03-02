# Example - Invoke

This example utilizes a receiver and a caller for the OnInvoke / Invoke functionality. It will create a gRPC server and bind the OnInvoke method, which gets called after a client sends a direct method invocation.

> **Note:** Make sure to use the latest proto bindings

## Running

To run this example, the following code can be utilized:

```bash
# 1. Start Receiver (expose gRPC server receiver on port 50051)
dapr run --app-id invoke-receiver --protocol grpc --app-port 50051 python invoke-receiver.py

# 2. Start Caller
dapr run --app-id invoke-caller --protocol grpc python invoke-caller.py
```