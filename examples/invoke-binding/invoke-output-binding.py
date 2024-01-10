import json
import time

from dapr.clients import DaprClient

with DaprClient() as d:
    n = 0
    while True:
        n += 1
        req_data = {'id': n, 'message': 'hello world'}

        print(f'Sending message id: {req_data["id"]}, message "{req_data["message"]}"', flush=True)

        # Create a typed message with content type and body
        resp = d.invoke_binding('kafkaBinding', 'create', json.dumps(req_data))

        time.sleep(1)
