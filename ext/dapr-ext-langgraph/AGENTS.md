# AGENTS.md — dapr-ext-langgraph

The LangGraph extension provides a Dapr-backed checkpoint saver for [LangGraph](https://langchain-ai.github.io/langgraph/) workflows, persisting workflow state to any Dapr state store.

## Source layout

```
ext/dapr-ext-langgraph/
├── setup.cfg                          # Deps: dapr, langgraph, langchain, python-ulid, msgpack
├── setup.py
├── tests/
│   └── test_checkpointer.py           # Unit tests with mocked DaprClient
└── dapr/ext/langgraph/
    ├── __init__.py                    # Exports: DaprCheckpointer
    ├── dapr_checkpointer.py           # Main implementation (~420 lines)
    └── version.py
```

## Public API

```python
from dapr.ext.langgraph import DaprCheckpointer
```

### DaprCheckpointer (`dapr_checkpointer.py`)

Extends `langgraph.checkpoint.base.BaseCheckpointSaver[Checkpoint]`.

```python
cp = DaprCheckpointer(store_name='statestore', key_prefix='lg')
config = {'configurable': {'thread_id': 't1'}}

# Save checkpoint
next_config = cp.put(config, checkpoint, metadata, new_versions)

# Retrieve latest
tuple = cp.get_tuple(config)  # → Optional[CheckpointTuple]

# List all
all_checkpoints = cp.list(config)  # → list[CheckpointTuple]

# Store intermediate writes
cp.put_writes(config, writes=[(channel, value)], task_id='task1')

# Delete thread
cp.delete_thread(config)
```

### Key methods

**`put(config, checkpoint, metadata, new_versions)`** — Serializes and saves a checkpoint to the state store. Creates two keys: the checkpoint data key (`checkpoint:{thread_id}:{ns}:{id}`) and a "latest" pointer key (`checkpoint_latest:{thread_id}:{ns}`).

**`get_tuple(config)`** — Retrieves the most recent checkpoint. Follows the latest pointer, then fetches the actual data. Handles both binary (msgpack) and JSON formats. Performs recursive byte decoding and LangChain message type conversion (`HumanMessage`, `AIMessage`, `ToolMessage`).

**`put_writes(config, writes, task_id, task_path)`** — Stores intermediate channel writes linked to a checkpoint. Each write is serialized with `serde.dumps_typed()` and base64-encoded.

**`list(config)`** — Lists all checkpoints for a thread using a registry key (`dapr_checkpoint_registry`).

**`delete_thread(config)`** — Deletes checkpoint data and removes it from the registry.

## Data storage schema

| Key pattern | Contents |
|-------------|----------|
| `checkpoint:{thread_id}:{ns}:{id}` | Full checkpoint data (channel values, versions, metadata) |
| `checkpoint_latest:{thread_id}:{ns}` | Points to the latest checkpoint key |
| `dapr_checkpoint_registry` | List of all checkpoint keys (for `list()`) |

## Dependencies

- `dapr >= 1.17.0.dev`
- `langgraph >= 0.3.6`
- `langchain >= 0.1.17`
- `python-ulid >= 3.0.0` (for checkpoint ID ordering)
- `msgpack-python >= 0.4.5` (for binary serialization)

## Testing

```bash
python -m unittest discover -v ./ext/dapr-ext-langgraph/tests
```

6 test cases using `@mock.patch('dapr.ext.langgraph.dapr_checkpointer.DaprClient')`:
- `test_get_tuple_returns_checkpoint` / `test_get_tuple_none_when_missing`
- `test_put_saves_checkpoint_and_registry`
- `test_put_writes_updates_channel_values`
- `test_list_returns_all_checkpoints`
- `test_delete_thread_removes_key_and_updates_registry`

## Key details

- **Serialization**: Uses `JsonPlusSerializer` from LangGraph for complex types, with msgpack for binary optimization and base64 for blob encoding.
- **Message conversion**: Handles LangChain message types (`HumanMessage`, `AIMessage`, `ToolMessage`) during deserialization from msgpack `ExtType` objects.
- **State store agnostic**: Works with any Dapr state store backend (Redis, Cosmos DB, PostgreSQL, etc.) — all state operations go through `DaprClient.save_state()` / `get_state()` / `delete_state()`.
- **Thread isolation**: Each workflow thread is namespaced by `thread_id` in all keys.
- **Numeric string conversion**: `_decode_bytes` converts numeric strings to `int` for LangGraph `channel_version` comparisons.
