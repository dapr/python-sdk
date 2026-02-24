# AGENTS.md — dapr-ext-strands

The Strands extension provides distributed session management for [Strands Agents](https://github.com/strands-agents/strands-agents), persisting sessions, agents, and messages to any Dapr state store with optional TTL and consistency controls.

## Source layout

```
ext/dapr-ext-strands/
├── setup.cfg                              # Deps: dapr, strands-agents, strands-agents-tools, python-ulid, msgpack
├── setup.py
├── tests/
│   └── test_session_manager.py            # Unit tests with mocked DaprClient
└── dapr/ext/strands/
    ├── __init__.py                        # Exports: DaprSessionManager
    ├── dapr_session_manager.py            # Main implementation (~550 lines)
    └── version.py
```

## Public API

```python
from dapr.ext.strands import DaprSessionManager
```

### DaprSessionManager (`dapr_session_manager.py`)

Extends both `RepositorySessionManager` and `SessionRepository` from the Strands agents framework.

**Constructor:**
```python
manager = DaprSessionManager(
    session_id='my-session',
    state_store_name='statestore',
    dapr_client=client,          # DaprClient instance
    ttl=3600,                    # Optional: TTL in seconds
    consistency='eventual',      # 'eventual' (default) or 'strong'
)
```

**Factory method:**
```python
manager = DaprSessionManager.from_address(
    session_id='my-session',
    state_store_name='statestore',
    dapr_address='localhost:50001',  # Auto-creates DaprClient
)
```

### Methods

**Session operations:**
- `create_session(session)` → `Session` — creates new session (raises if exists)
- `read_session(session_id)` → `Optional[Session]`
- `delete_session(session_id)` — cascade deletes session + all agents + messages

**Agent operations:**
- `create_agent(session_id, session_agent)` — creates agent, initializes empty messages, updates manifest
- `read_agent(session_id, agent_id)` → `Optional[SessionAgent]`
- `update_agent(session_id, session_agent)` — preserves original `created_at`

**Message operations:**
- `create_message(session_id, agent_id, message)` — appends to message list
- `read_message(session_id, agent_id, message_id)` → `Optional[SessionMessage]`
- `update_message(session_id, agent_id, message)` — preserves original `created_at`
- `list_messages(session_id, agent_id, limit=None, offset=0)` → `List[SessionMessage]`

**Lifecycle:**
- `close()` — closes DaprClient if owned by this manager

## State store key schema

| Key pattern | Contents |
|-------------|----------|
| `{session_id}:session` | Session metadata (JSON) |
| `{session_id}:agents:{agent_id}` | Agent metadata (JSON) |
| `{session_id}:messages:{agent_id}` | Message list: `{"messages": [...]}` (JSON) |
| `{session_id}:manifest` | Agent ID registry: `{"agents": [...]}` (used for cascade deletion) |

## Dependencies

- `dapr >= 1.17.0.dev`
- `strands-agents` — Strands agents framework
- `strands-agents-tools` — Strands agent tools
- `python-ulid >= 3.0.0`
- `msgpack-python >= 0.4.5`

## Testing

```bash
python -m unittest discover -v ./ext/dapr-ext-strands/tests
```

8 test cases using `@mock.patch('dapr.ext.strands.dapr_session_manager.DaprClient')`:
- `test_create_and_read_session`, `test_create_session_raises_if_exists`
- `test_create_and_read_agent`, `test_update_agent_preserves_created_at`
- `test_create_and_read_message`, `test_update_message_preserves_created_at`
- `test_delete_session_deletes_agents_and_messages` (verifies cascade: 6 delete calls for 2 agents)
- `test_close_only_closes_owned_client`

## Key details

- **ID validation**: Session IDs and agent IDs are validated via `strands._identifier.validate()` — path separators (`/`, `\`) are rejected.
- **Manifest pattern**: A manifest key tracks all agent IDs per session, enabling cascade deletion without scanning.
- **TTL support**: Optional time-to-live via Dapr state metadata (`ttlInSeconds`).
- **Consistency levels**: Maps to Dapr's `Consistency.eventual` / `Consistency.strong` via `StateOptions`.
- **Client ownership**: The `_owns_client` flag tracks whether `DaprSessionManager` created its own client (via `from_address`) or received one externally. Only owned clients are closed by `close()`.
- **Timestamp preservation**: `update_agent` and `update_message` read the existing record first to preserve the original `created_at` timestamp.
- **All errors are `SessionException`**: All Dapr state operation failures are wrapped in Strands' `SessionException`.
