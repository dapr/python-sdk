
"""
dapr run --protocol grpc --grpc-port=50001 python example.py
"""

import grpc
import os

from dapr.proto import api_v1, api_service_v1, common_v1
from google.protobuf.any_pb2 import Any

# Get port from environment variable.
port = os.getenv('DAPR_GRPC_PORT', '50001')
daprUri = 'localhost:' + port
channel = grpc.insecure_channel(daprUri)

client = api_service_v1.DaprStub(channel)
client.PublishEvent(api_v1.PublishEventRequest(topic='sith', data='lala'.encode('utf-8')))
print('Published!')

key = 'mykey'
storeName = 'statestore'
req = common_v1.StateSaveRequest(key=key, value='my state'.encode('utf-8'))
state = api_v1.SaveStateRequest(store_name=storeName, requests=[req])

client.SaveState(state)
print('Saved!')

resp = client.GetState(api_v1.GetStateRequest(store_name=storeName, key=key))
print('Got!')
print(resp)

resp = client.DeleteState(api_v1.DeleteStateRequest(store_name=storeName, key=key))
print('Deleted!')

channel.close()
