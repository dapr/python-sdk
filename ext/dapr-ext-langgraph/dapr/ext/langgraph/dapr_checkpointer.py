import base64
import json
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

import msgpack
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from ulid import ULID

from dapr.clients import DaprClient
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


class DaprCheckpointer(BaseCheckpointSaver[Checkpoint]):
    """
    Dapr-backed LangGraph Checkpointer that persists checkpoints to a Dapr state store.
    Compatible with LangGraph >= 0.3.6 and LangChain Core >= 1.0.0.
    """

    REGISTRY_KEY = 'dapr_checkpoint_registry'

    def __init__(self, store_name: str, key_prefix: str):
        self.store_name = store_name
        self.key_prefix = key_prefix
        self.serde = JsonPlusSerializer()
        self.client = DaprClient()
        self._key_cache: Dict[str, str] = {}

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

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id = config['configurable']['thread_id']
        checkpoint_ns = config['configurable'].get('checkpoint_ns', '')
        config_checkpoint_id = config['configurable'].get('checkpoint_id', '')
        thread_ts = config['configurable'].get('thread_ts', '')

        checkpoint_id = config_checkpoint_id or thread_ts or checkpoint.get('id', '')

        parent_checkpoint_id = None
        if (
            checkpoint.get('id')
            and config_checkpoint_id
            and checkpoint.get('id') != config_checkpoint_id
        ):
            parent_checkpoint_id = config_checkpoint_id
            checkpoint_id = checkpoint['id']

        storage_safe_thread_id = self._safe_id(thread_id)
        storage_safe_checkpoint_ns = self._safe_ns(checkpoint_ns)
        storage_safe_checkpoint_id = self._safe_id(checkpoint_id)

        copy = checkpoint.copy()
        next_config = {
            'configurable': {
                'thread_id': thread_id,
                'checkpoint_ns': checkpoint_ns,
                'checkpoint_id': checkpoint_id,
            }
        }

        checkpoint_ts = None
        if checkpoint_id:
            try:
                ulid_obj = ULID.from_str(checkpoint_id)
                checkpoint_ts = ulid_obj.timestamp
            except Exception:
                checkpoint_ts = time.time() * 1000

        checkpoint_data = {
            'thread_id': storage_safe_thread_id,
            'checkpoint_ns': storage_safe_checkpoint_ns,
            'checkpoint_id': storage_safe_checkpoint_id,
            'parent_checkpoint_id': (
                '00000000-0000-0000-0000-000000000000'
                if (parent_checkpoint_id if parent_checkpoint_id else '') == ''
                else parent_checkpoint_id
            ),
            'checkpoint_ts': checkpoint_ts,
            'checkpoint': self._dump_checkpoint(copy),
            'metadata': self._dump_metadata(metadata),
            'has_writes': False,
        }

        if all(key in metadata for key in ['source', 'step']):
            checkpoint_data['source'] = metadata['source']
            checkpoint_data['step'] = metadata['step']

        checkpoint_key = self._make_safe_checkpoint_key(
            thread_id=thread_id, checkpoint_ns=checkpoint_ns, checkpoint_id=checkpoint_id
        )

        _, data = self.serde.dumps_typed(checkpoint_data)
        self.client.save_state(store_name=self.store_name, key=checkpoint_key, value=data)

        latest_pointer_key = (
            f'checkpoint_latest:{storage_safe_thread_id}:{storage_safe_checkpoint_ns}'
        )

        self.client.save_state(
            store_name=self.store_name, key=latest_pointer_key, value=checkpoint_key
        )

        return next_config

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
        task_path: str = '',
    ) -> None:
        """Store intermediate writes linked to a checkpoint with integrated key registry."""
        thread_id = config['configurable']['thread_id']
        checkpoint_ns = config['configurable'].get('checkpoint_ns', '')
        checkpoint_id = config['configurable'].get('checkpoint_id', '')
        storage_safe_thread_id = (self._safe_id(thread_id),)
        storage_safe_checkpoint_ns = self._safe_ns(checkpoint_ns)

        writes_objects: List[Dict[str, Any]] = []
        for idx, (channel, value) in enumerate(writes):
            type_, blob = self.serde.dumps_typed(value)
            write_obj: Dict[str, Any] = {
                'thread_id': storage_safe_thread_id,
                'checkpoint_ns': storage_safe_checkpoint_ns,
                'checkpoint_id': self._safe_id(checkpoint_id),
                'task_id': task_id,
                'task_path': task_path,
                'idx': WRITES_IDX_MAP.get(channel, idx),
                'channel': channel,
                'type': type_,
                'blob': self._encode_blob(blob),
            }
            writes_objects.append(write_obj)

        for write_obj in writes_objects:
            idx_value = write_obj['idx']
            assert isinstance(idx_value, int)
            key = self._make_safe_checkpoint_key(
                thread_id=thread_id, checkpoint_ns=checkpoint_ns, checkpoint_id=checkpoint_id
            )

            self.client.save_state(store_name=self.store_name, key=key, value=json.dumps(write_obj))

            checkpoint_key = self._make_safe_checkpoint_key(
                thread_id=thread_id, checkpoint_ns=checkpoint_ns, checkpoint_id=checkpoint_id
            )

            latest_pointer_key = (
                f'checkpoint_latest:{storage_safe_thread_id}:{storage_safe_checkpoint_ns}'
            )

            self.client.save_state(
                store_name=self.store_name, key=latest_pointer_key, value=checkpoint_key
            )

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

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config['configurable']['thread_id']
        checkpoint_ns = config['configurable'].get('checkpoint_ns', '')

        storage_safe_thread_id = self._safe_id(thread_id)
        storage_safe_checkpoint_ns = self._safe_ns(checkpoint_ns)

        key = ':'.join(
            [
                'checkpoint_latest',
                storage_safe_thread_id,
                storage_safe_checkpoint_ns,
            ]
        )

        # First we extract the latest checkpoint key
        checkpoint_key = self.client.get_state(store_name=self.store_name, key=key)
        if not checkpoint_key.data:
            return None

        # To then derive the checkpoint data
        checkpoint_data = self.client.get_state(
            store_name=self.store_name,
            # checkpoint_key.data can either be str or bytes
            key=checkpoint_key.data.decode()
            if isinstance(checkpoint_key.data, bytes)
            else checkpoint_key.data,
        )

        if not checkpoint_data.data:
            return None

        if isinstance(checkpoint_data.data, bytes):
            unpacked = msgpack.unpackb(checkpoint_data.data)

            checkpoint_values = unpacked[b'checkpoint']
            channel_values = checkpoint_values[b'channel_values']

            decoded_messages = []
            for item in channel_values[b'messages']:
                if isinstance(item, msgpack.ExtType):
                    decoded_messages.append(
                        self._convert_checkpoint_message(
                            self._load_metadata(msgpack.unpackb(item.data))
                        )
                    )
                else:
                    decoded_messages.append(item)

            checkpoint_values[b'channel_values'][b'messages'] = decoded_messages

            mdata = unpacked.get(b'metadata')
            if isinstance(mdata, bytes):
                mdata = self._load_metadata(msgpack.unpackb(mdata))

            metadata = {
                k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
                for k, v in mdata.items()
            }

            checkpoint_obj = Checkpoint(
                **{
                    key.decode() if isinstance(key, bytes) else key: value
                    for key, value in checkpoint_values.items()
                }
            )

            checkpoint = self._decode_bytes(checkpoint_obj)
        elif isinstance(checkpoint_data.data, str):
            unpacked = json.loads(checkpoint_data.data)
            checkpoint = unpacked.get('checkpoint', None)
            metadata = unpacked.get('metadata', None)

            if not metadata or not checkpoint:
                return None
        else:
            return None

        return CheckpointTuple(
            config=config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=None,
            pending_writes=[],
        )

    def _safe_id(self, id) -> str:
        return '00000000-0000-0000-0000-000000000000' if id == '' else id

    def _safe_ns(self, ns) -> str:
        return '__empty__' if ns == '' else ns

    def _convert_checkpoint_message(self, msg_item):
        _, _, data_dict, _ = msg_item
        data_dict = self._decode_bytes(data_dict)

        msg_type = data_dict.get('type')

        if msg_type == 'human':
            return HumanMessage(**data_dict)
        elif msg_type == 'ai':
            return AIMessage(**data_dict)
        elif msg_type == 'tool':
            return ToolMessage(**data_dict)
        else:
            raise ValueError(f'Unknown message type: {msg_type}')

    def _decode_bytes(self, obj):
        if isinstance(obj, bytes):
            try:
                s = obj.decode()
                # Convert to int if it's a number, the unpacked channel_version holds \xa1 which unpacks as strings
                # LangGraph needs Ints for '>' comparison
                if s.isdigit():
                    return int(s)
                return s
            except Exception:
                return obj
        if isinstance(obj, dict):
            return {self._decode_bytes(k): self._decode_bytes(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._decode_bytes(v) for v in obj]
        if isinstance(obj, tuple):
            return tuple(self._decode_bytes(v) for v in obj)
        return obj

    def _encode_blob(self, blob: Any) -> str:
        if isinstance(blob, bytes):
            return base64.b64encode(blob).decode()
        return blob

    def _dump_checkpoint(self, checkpoint: Checkpoint) -> dict[str, Any]:
        type_, data = self.serde.dumps_typed(checkpoint)

        if type_ == 'json':
            checkpoint_data = cast(dict, json.loads(data))
        else:
            checkpoint_data = cast(dict, self.serde.loads_typed((type_, data)))

            if 'channel_values' in checkpoint_data:
                for key, value in checkpoint_data['channel_values'].items():
                    if isinstance(value, bytes):
                        checkpoint_data['channel_values'][key] = {
                            '__bytes__': self._encode_blob(value)
                        }

        if 'channel_versions' in checkpoint_data:
            checkpoint_data['channel_versions'] = {
                k: str(v) for k, v in checkpoint_data['channel_versions'].items()
            }

        return {'type': type_, **checkpoint_data, 'pending_sends': []}

    def _load_metadata(self, metadata: dict[str, Any]) -> CheckpointMetadata:
        type_str, data_bytes = self.serde.dumps_typed(metadata)
        return self.serde.loads_typed((type_str, data_bytes))

    def _dump_metadata(self, metadata: CheckpointMetadata) -> str:
        _, serialized_bytes = self.serde.dumps_typed(metadata)
        return serialized_bytes

    def _make_safe_checkpoint_key(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> str:
        return ':'.join(
            [
                'checkpoint',
                thread_id,
                checkpoint_ns,
                checkpoint_id,
            ]
        )
