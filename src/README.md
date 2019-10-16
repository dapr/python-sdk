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

You can find a complete example at https://github.com/dapr/python-sdk
