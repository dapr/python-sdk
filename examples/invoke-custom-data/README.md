# Example - Invoke

This example utilizes a receiver and a caller for the OnInvoke / Invoke functionality. It will create a gRPC server and bind the OnInvoke method, which gets called after a client sends a direct method invocation.

> **Note:** Make sure to use the latest proto bindings and have them available under `dapr_pb2` and `daprclient_pb2`

## Install Dapr python-SDK

```bash
pip3 install dapr dapr-ext-grpc
```

## How To - Run Example

To run this example, the following steps should be followed:

```bash
# 1. Compile Protobuf for Custom Response
python -m grpc_tools.protoc --proto_path=./proto/ --python_out=./proto/ --grpc_python_out=./proto/ ./proto/response.proto

# 2. Start Receiver (expose gRPC server receiver on port 50051)
dapr run --app-id invoke-receiver --app-protocol grpc --app-port 50051 python3 invoke-receiver.py

# 3. Start Caller
dapr run --app-id invoke-caller --app-protocol grpc python invoke-caller.py
```
