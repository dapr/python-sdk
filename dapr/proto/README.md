## Generating gRPC interface and Protobuf

We use [uv](https://docs.astral.sh/uv/) to manage the regen environment.

### Linux and MacOS

Run the following commands:

```sh
uv sync
export DAPR_BRANCH=release-1.16 # Optional, defaults to master
uv run ./tools/regen_grpcclient.sh
```

> Note: To use the newly generated protobuf stubs and gRPC interface replace `daprd` with `edge` version of `daprd` built from master branch. Refer [this](https://github.com/dapr/dapr/blob/master/docs/development/developing-dapr.md#build-the-dapr-binaries) for instructions on how to build `daprd` from master.
