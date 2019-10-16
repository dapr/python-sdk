## Python client for dapr.
The repository generates following package
- dapr

### Installing package
```sh
pip install dapr
```
*Note*: Depending on your OS, you may want to use pip3 instead of pip.

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
dapr run --protocol grpc --grpc-port=50001 python example.py
```
*Note*: Depending on your OS, you may want to use python3 instead of python.


### Generate package
Package can be generated as:
```sh
cd src
python setup.py sdist bdist_wheel
```
*Note*: Depending on your OS, you may want to use python3 instead of python.

The package will be generated in src/dist directory.
For more information on generating packages, see python documentation at https://packaging.python.org/tutorials/packaging-projects/