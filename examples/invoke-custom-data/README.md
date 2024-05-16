# Example - Invoke a service with custom data

This example utilizes a receiver and a caller for the OnInvoke / Invoke functionality. It will create a gRPC server and bind the OnInvoke method, which gets called after a client sends a direct method invocation.

> **Note:** Make sure to use the latest proto bindings and have them available under `dapr_pb2` and `daprclient_pb2`

## Pre-requisites

- [Dapr CLI and initialized environment](https://docs.dapr.io/getting-started)
- [Install Python 3.8+](https://www.python.org/downloads/)

## Install Dapr python-SDK

<!-- Our CI/CD pipeline automatically installs the correct version, so we can skip this step in the automation -->

```bash
pip3 install dapr dapr-ext-grpc
```

## How To - Run Example

To run this example, the following steps should be followed:


1. Compile Protobuf for Custom Response

   ```bash
   python3 -m grpc_tools.protoc --proto_path=./proto/ --python_out=./proto/    --grpc_python_out=./proto/ ./proto/response.proto
   ```

2. Start Receiver (expose gRPC server receiver on port 50051)

<!-- STEP
name: Run receiver
expected_stdout_lines:
  - '== APP == SOME_DATA'
background: true
sleep: 5
-->

   ```bash
   dapr run --app-id invoke-receiver --app-protocol grpc --app-port 50051 python3 invoke-receiver.py
   ```

<!-- END_STEP -->

3. Start Caller

<!-- STEP
name: Run caller
expected_stdout_lines:
  - '== APP == isSuccess: true'
  - '== APP == code: 200'
  - '== APP == message: "Hello World - Success!"'
  - '✅  Exited App successfully'
background: true
sleep: 5
-->

   ```bash
   dapr run --app-id invoke-caller --app-protocol grpc python3 invoke-caller.py
   ```

<!-- END_STEP -->

Expected output from caller:

   ```
   == APP == isSuccess: true
   == APP == code: 200
   == APP == message: "Hello World - Success!"
   == APP == 
   ```

Expected output from receiver: 

   ```
   == APP == {'user-agent': ['grpc-go/1.33.1'], 'x-forwarded-host':    ['MyPC'], 'x-forwarded-for': ['192.   168.1.3'], 'forwarded': ['for=192.168.1.3;by=192.168.1.3;   host=MyPC'], 'grpc-trace-bin':    [b'\x00\x00\x90Zc\x17\xaav?5)L\xcd]>.   \x88>\x01\x81\xe9\x9c\xbd\x01x\xfc\xc5\x02\x01']}
   == APP == SOME_DATA
   ```

4. Cleanup

<!-- STEP
expected_stdout_lines: 
  - '✅  app stopped successfully: invoke-receiver'
name: Shutdown dapr
-->

```bash
dapr stop --app-id invoke-receiver
```

<!-- END_STEP -->
