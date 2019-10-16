from dapr import dapr_pb2 as messages
from dapr import dapr_pb2_grpc as services
import grpc
import os
from google.protobuf.any_pb2 import Any

# Get port from environment variable.
port = os.getenv('DAPR_GRPC_PORT', '5001')
daprUri = 'localhost:' + port
channel = grpc.insecure_channel(daprUri)

client = services.DaprStub(channel)
data = Any(value='lala'.encode('utf-8'))
client.PublishEvent(messages.PublishEventEnvelope(topic='sith', data=data))
print('Published!')

key = 'mykey'
req = messages.StateRequest(key=key, value=Any(value='my state'.encode('utf-8')))
state = messages.SaveStateEnvelope(requests=[req])

client.SaveState(state)
print('Saved!')

resp = client.GetState(messages.GetStateEnvelope(key=key))
print('Got!')
print(resp)

resp = client.DeleteState(messages.DeleteStateEnvelope(key=key))
print('Deleted!')

channel.close()

