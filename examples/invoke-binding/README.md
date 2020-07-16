# Example - InvokeBinding

This example utilizes a publisher and a receiver for the InvokeBinding / OnBindingEvent / ListInputBindings functionality. It will create a gRPC server and bind the OnBindingEvent method, which gets called after a publisher sends a message to a kafka binding.

> **Note:** Make sure to use the latest proto bindings

## Running

To run this example, the following code can be utilized:

```bash
# 1. Start the kafka containers using docker-compose 
docker-compose -f ./docker-compose-single-kafka.yml up -d

# 2. Start Receiver (expose gRPC server receiver on port 50051) 
dapr run --app-id receiver --protocol grpc --app-port 50051 --components-path ./components python3 invoke-input-binding.py

# 3. Start Publisher
dapr run --app-id publisher --protocol grpc --components-path ./components python3 invoke-output-binding.py
```

## Cleanup

The dapr apps can be stopped by calling stop or terminating the process. For kafka cleanup, run the following code:

```bash
docker-compose -f ./docker-compose-single-kafka.yml down
```