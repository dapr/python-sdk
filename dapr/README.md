## Generating gRPC interface and Protobuf

As a good practice create a python virtual environment:

```sh
python3 -m venv <env_name>
source <env_name>/bin/activate
```

### Linux and MacOS

Run the following commands:

```sh
pip3 install -r grpc_requirements
sudo chmod +x protobuf.sh
. ./protobuf.sh
```

### Windows

Run the following commands in powershell:

```sh
pip3 install -r grpc_requirements
.\protobuf.ps1
```

Add absolute path of `src` folder as `PYTHONPATH` environment variable.

> Note: To use the newly generated protobuf stubs and gRPC interface replace `daprd` with `edge` version of `daprd` built from master branch. Refer [this](https://github.com/dapr/dapr/blob/master/docs/development/developing-dapr.md#build-the-dapr-binaries) for instructions on how to build `daprd` from master.
