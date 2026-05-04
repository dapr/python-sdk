## Generating gRPC interface and Protobuf

### Linux and MacOS

Run the following commands:

```sh
uv sync --all-packages --group dev
export DAPR_BRANCH=release-1.17 # Optional, defaults to master
uv run ./tools/regen_grpcclient.sh
```

> Note: To use the newly generated protobuf stubs and gRPC interface replace `daprd` with `edge` version of `daprd` built from master branch. Refer [this](https://github.com/dapr/dapr/blob/master/docs/development/developing-dapr.md#build-the-dapr-binaries) for instructions on how to build `daprd` from master.
