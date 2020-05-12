# Dapr SDK for Python
This is the Dapr SDK for Python, based on the auto-generated proto client.<br>

For more info on Dapr and gRPC, visit [this link](https://github.com/dapr/docs/tree/master/howto/create-grpc-app).

The repository generates following package
- dapr

### Installing package
```sh
pip install dapr-client
```
*Note*: Depending on your OS, you may want to use pip3 instead of pip.

### Example code
A client can be created as follows:

```python
from dapr.proto.dapr.v1 import dapr_pb2 as messages
from dapr.proto.dapr.v1 import dapr_pb2_grpc as services
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


### Generating package
Package can be generated as:
```sh
cd src
python setup.py sdist bdist_wheel
```
*Note*: Depending on your OS, you may want to use python3 instead of python.

The package will be generated in src/dist directory.
For more information on generating packages, see python documentation at https://packaging.python.org/tutorials/packaging-projects/

### Generating gRPC interface and proto buf

As a good practice create a python virtual environment:

```sh
python3 -m venv <env_name>
source <env_name>/bin/activate
```

## Linux and MacOS
Run the following commands:
```sh
pip3 install -r grpc_requirements
sudo chmod +x protobuf.sh
. ./protobuf.sh
```
## Windows
Run the following commands in powershell:
```sh
pip3 install -r grpc_requirements
.\protobuf.ps1
```
Add absolute path of `src` folder as `PYTHONPATH` environment variable.

> Note: To use the newly generated proto buf stubs and gRPC interface replace `daprd` with `edge` version of `daprd` built from master branch. Refer [this](https://github.com/dapr/dapr/blob/master/docs/development/developing-dapr.md#build-the-dapr-binaries) for instructions on how to build `daprd` from master. 