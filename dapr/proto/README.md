## Generating gRPC interface and Protobuf

As a good practice create a python virtual environment:

```sh
python3 -m venv <env_name>
source <env_name>/bin/activate
```

### Linux and MacOS

Run the following commands:

```sh
pip3 install -r tools/requirements.txt
./tools/regen_grpcclient.sh
```

> Note: To use the newly generated protobuf stubs and gRPC interface replace `daprd` with `edge` version of `daprd` built from master branch. Refer [this](https://github.com/dapr/dapr/blob/master/docs/development/developing-dapr.md#build-the-dapr-binaries) for instructions on how to build `daprd` from master.
