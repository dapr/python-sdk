# Binary store (alpha)

Upload, download, overwrite, and delete binary files through the Dapr binary-store
API. Both examples use an in-memory component, so they need no cloud credentials.
Its contents are lost when the sidecar stops.

## Prerequisites

- Python 3.10 or later
- A Dapr Python SDK build containing the binary-store API
- Dapr runtime 1.19 or later (preview testing: 1.19.0-rc.3 or later)
- Dapr CLI with a locally initialized runtime (`dapr init`)

From the repository root, install the SDK and development dependencies:

```bash
uv sync --frozen --all-packages --group dev
```

## Run

From this directory, run either example with the installed SDK environment active:

```bash
dapr run --app-id binary-store --resources-path ./components -- python3 binary_store.py
dapr run --app-id binary-store-async --resources-path ./components -- python3 binary_store_async.py
```

Expected application output for each:

```text
Binary file round trip: 262144 bytes
Overwritten file: replaced
Binary file deleted
```

## API behavior

`set_binary_file_alpha1(store_name, file_name, data, *, overwrite=False,
chunk_size=32768, timeout=None)` accepts `bytes` or an open binary reader. It reads
from the current position, leaves the caller's reader open, and sends bounded
chunks. Creating an existing file fails unless `overwrite=True`. Async file reads
run in a thread; cancelling the operation cannot interrupt a blocking file read
already in progress.

`get_binary_file_alpha1(store_name, file_name, *, timeout=None)` returns a download
response. Iterate over bytes or use `read(size)` for bounded reads. `read()` buffers
the remaining file in memory, so use it for small files. Partial reads and iteration
share one cursor; use one consumer per response. Get failures surface while reading.
Use `with`/`close()` (async: `async with`/`aclose()`) to cancel an unfinished download.
The async get method must first be awaited, as shown in the example.

`delete_binary_file_alpha1(store_name, file_name, *, timeout=None)` deletes a file.
Missing-file behavior depends on the component; the in-memory component reports
`NOT_FOUND` for both get and delete. The optional timeout on every method covers
the entire RPC, including download consumption; when omitted, the SDK uses
`DAPR_API_TIMEOUT_SECONDS` if configured. The SDK does not replay binary-store
operations. gRPC failures use `DaprGrpcError` and preserve the status supplied by
the transport. Some gRPC async versions can report an early upload rejection as
`INTERNAL` when a write races the server closing the stream
([grpc/grpc#36066](https://github.com/grpc/grpc/issues/36066)).

All three methods emit an alpha `UserWarning`. These APIs may change.
