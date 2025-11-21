import json
from typing import Any, Sequence, Tuple

from langchain_core.load import dumps
from langchain_core.runnables import RunnableConfig

from dapr.clients import DaprClient
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointTuple


class DaprCheckpointer(BaseCheckpointSaver[Checkpoint]):
    """
    Dapr-backed LangGraph Checkpointer that persists checkpoints to a Dapr state store.
    Compatible with LangGraph >= 0.3.6 and LangChain Core >= 1.0.0.
    """

    REGISTRY_KEY = 'dapr_checkpoint_registry'

    def __init__(self, store_name: str, key_prefix: str):
        self.store_name = store_name
        self.key_prefix = key_prefix
        self.client = DaprClient()

    # helper: construct Dapr key for a thread
    def _get_key(self, config: RunnableConfig) -> str:
        thread_id = None

        if isinstance(config, dict):
            thread_id = config.get('configurable', {}).get('thread_id')

            if not thread_id:
                thread_id = config.get('thread_id')

        if not thread_id:
            thread_id = 'default'

        return f'{self.key_prefix}:{thread_id}'

    # restore a checkpoint
    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        key = self._get_key(config)

        resp = self.client.get_state(store_name=self.store_name, key=key)
        if not resp.data:
            return None

        wrapper = json.loads(resp.data)
        cp_data = wrapper.get('checkpoint', wrapper)
        metadata = wrapper.get('metadata', {'step': 0})
        if 'step' not in metadata:
            metadata['step'] = 0

        cp = Checkpoint(**cp_data)
        return CheckpointTuple(
            config=config,
            checkpoint=cp,
            parent_config=None,
            metadata=metadata,
        )

    # save a full checkpoint snapshot
    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        parent_config: RunnableConfig | None,
        metadata: dict[str, Any],
    ) -> None:
        key = self._get_key(config)

        checkpoint_serializable = {
            'v': checkpoint['v'],
            'id': checkpoint['id'],
            'ts': checkpoint['ts'],
            'channel_values': checkpoint['channel_values'],
            'channel_versions': checkpoint['channel_versions'],
            'versions_seen': checkpoint['versions_seen'],
        }

        wrapper = {'checkpoint': checkpoint_serializable, 'metadata': metadata}

        self.client.save_state(self.store_name, key, dumps(wrapper))

        reg_resp = self.client.get_state(store_name=self.store_name, key=self.REGISTRY_KEY)
        registry = json.loads(reg_resp.data) if reg_resp.data else []

        if key not in registry:
            registry.append(key)
            self.client.save_state(self.store_name, self.REGISTRY_KEY, json.dumps(registry))

    # incremental persistence (for streamed runs)
    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
        task_path: str = '',
    ) -> None:
        _ = task_id, task_path

        key = self._get_key(config)

        resp = self.client.get_state(store_name=self.store_name, key=key)
        if not resp.data:
            return

        wrapper = json.loads(resp.data)
        cp = wrapper.get('checkpoint', {})

        for field, value in writes:
            cp['channel_values'][field] = value

        wrapper['checkpoint'] = cp
        self.client.save_state(self.store_name, key, json.dumps(wrapper))

    # enumerate all saved checkpoints
    def list(self, config: RunnableConfig) -> list[CheckpointTuple]:
        reg_resp = self.client.get_state(store_name=self.store_name, key=self.REGISTRY_KEY)
        if not reg_resp.data:
            return []

        keys = json.loads(reg_resp.data)
        checkpoints: list[CheckpointTuple] = []

        for key in keys:
            cp_resp = self.client.get_state(store_name=self.store_name, key=key)
            if not cp_resp.data:
                continue

            wrapper = json.loads(cp_resp.data)
            cp_data = wrapper.get('checkpoint', {})
            metadata = wrapper.get('metadata', {})
            cp = Checkpoint(**cp_data)

            checkpoints.append(
                CheckpointTuple(
                    config=config,
                    checkpoint=cp,
                    parent_config=None,
                    metadata=metadata,
                )
            )

        return checkpoints

    # remove a checkpoint and update the registry
    def delete_thread(self, config: RunnableConfig) -> None:
        key = self._get_key(config)

        self.client.delete_state(store_name=self.store_name, key=key)

        reg_resp = self.client.get_state(store_name=self.store_name, key=self.REGISTRY_KEY)
        if not reg_resp.data:
            return

        registry = json.loads(reg_resp.data)

        if key in registry:
            registry.remove(key)
            self.client.save_state(
                store_name=self.store_name,
                key=self.REGISTRY_KEY,
                value=json.dumps(registry),
            )
