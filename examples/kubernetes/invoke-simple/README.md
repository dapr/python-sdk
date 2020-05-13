# Example - Kubernetes Simple Invoke

This example utilizes a receiver and a caller for the OnInvoke / Invoke functionality. It will create a gRPC server and bind the OnInvoke method, which gets called after a client sends a direct method invocation.

## Running

To run this example, the following code can be utilized:

```bash
# 0. Navigate to this script
cd examples/kubernetes/invoke-simple

# 1. Build Containers
./Scripts/build.sh demo-grpc-server $(pwd)/Server
./Scripts/build.sh demo-grpc-client $(pwd)/Client

# 2. Start Server (expose gRPC server receiver on port 50051)
./Scripts/start.sh demo-grpc-server

# 3. Start Client
./Scripts/start.sh demo-grpc-client
```