## Python client for dapr.

### Example code
A client can be created as follows:

```python
from dapr import dapr_pb2 as messages
from dapr import dapr_pb2_grpc as services
import grpc
from google.protobuf.any_pb2 import Any

channel = grpc.insecure_channel('localhost:50001')
client = services.DaprStub(channel)
```

You can find a complete example [here](https://github.com/dapr/python-sdk/blob/master/example.py)

### Running the code locally

You can execute this code using the local dapr runtime:

```sh
dapr run --grpc-port=50001 python3 example.py
```
