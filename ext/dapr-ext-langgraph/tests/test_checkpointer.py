# -*- coding: utf-8 -*-

import base64
import json
import unittest
from datetime import datetime
from unittest import mock

import msgpack
from dapr.ext.langgraph.dapr_checkpointer import DaprCheckpointer
from langgraph.checkpoint.base import Checkpoint


@mock.patch('dapr.ext.langgraph.dapr_checkpointer.DaprClient')
class DaprCheckpointerTest(unittest.TestCase):
    def setUp(self):
        self.store = 'statestore'
        self.prefix = 'lg'
        self.config = {'configurable': {'thread_id': 't1'}}

        self.checkpoint = Checkpoint(
            v=1,
            id='cp1',
            ts=datetime.now().timestamp(),
            channel_values={'a': 1},
            channel_versions={},
            versions_seen={},
        )

    def test_get_tuple_returns_checkpoint(self, mock_client_cls):
        mock_client = mock_client_cls.return_value

        wrapper = {
            'checkpoint': {
                'v': self.checkpoint['v'],
                'id': self.checkpoint['id'],
                'ts': self.checkpoint['ts'],
                'channel_values': self.checkpoint['channel_values'],
                'channel_versions': self.checkpoint['channel_versions'],
                'versions_seen': self.checkpoint['versions_seen'],
            },
            'metadata': {'step': 3},
        }
        mock_client.get_state.return_value.data = json.dumps(wrapper)

        cp = DaprCheckpointer(self.store, self.prefix)
        tup = cp.get_tuple(self.config)

        assert tup is not None
        assert tup.checkpoint['id'] == 'cp1'
        assert tup.metadata['step'] == 3

    def test_get_tuple_none_when_missing(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.get_state.return_value.data = None

        cp = DaprCheckpointer(self.store, self.prefix)
        assert cp.get_tuple(self.config) is None

    def test_put_saves_checkpoint_and_registry(self, mock_client_cls):
        mock_client = mock_client_cls.return_value

        mock_client.get_state.return_value.data = json.dumps([])

        cp = DaprCheckpointer(self.store, self.prefix)
        cp.put(self.config, self.checkpoint, {'step': 10}, None)

        first_call = mock_client.save_state.call_args_list[0]
        first_call_kwargs = first_call.kwargs
        assert first_call_kwargs['store_name'] == 'statestore'
        assert first_call_kwargs['key'] == 'checkpoint:t1::cp1'
        unpacked = msgpack.unpackb(first_call_kwargs['value'])  # We're packing bytes
        saved_payload = {}
        for k, v in unpacked.items():
            k = k.decode() if isinstance(k, bytes) else k
            if (
                k == 'checkpoint' or k == 'metadata'
            ):  # Need to convert b'' on checkpoint/metadata dict key/values
                if k == 'metadata':
                    v = msgpack.unpackb(v)  # Metadata value is packed
                val = {}
                for sk, sv in v.items():
                    sk = sk.decode() if isinstance(sk, bytes) else sk
                    sv = sv.decode() if isinstance(sv, bytes) else sv
                    val[sk] = sv
            else:
                val = v.decode() if isinstance(v, bytes) else v
            saved_payload[k] = val
        assert saved_payload['metadata']['step'] == 10

        second_call = mock_client.save_state.call_args_list[1]
        second_call_kwargs = second_call.kwargs
        assert second_call_kwargs['store_name'] == 'statestore'
        assert (
            second_call_kwargs['value'] == 'checkpoint:t1::cp1'
        )  # Here we're testing if the last checkpoint is the first_call above

    def test_put_writes_updates_channel_values(self, mock_client_cls):
        mock_client = mock_client_cls.return_value

        wrapper = {
            'checkpoint': {
                'v': 1,
                'id': 'cp1',
                'ts': 1000,
                'channel_values': {'a': 10},
                'channel_versions': {},
                'versions_seen': {},
            },
            'metadata': {},
        }
        mock_client.get_state.return_value.data = json.dumps(wrapper)

        cp = DaprCheckpointer(self.store, self.prefix)
        cp.put_writes(self.config, writes=[('a', 99)], task_id='task1')

        # save_state is called with updated checkpoint
        call = mock_client.save_state.call_args_list[0]
        # As we're using named input params we've got to fetch through kwargs
        kwargs = call.kwargs
        saved = json.loads(kwargs['value'])
        # As the value obj is base64 encoded in 'blob' we got to unpack it
        assert msgpack.unpackb(base64.b64decode(saved['blob'])) == 99

    def test_list_returns_all_checkpoints(self, mock_client_cls):
        mock_client = mock_client_cls.return_value

        registry = ['lg:t1']
        cp_wrapper = {
            'checkpoint': {
                'v': 1,
                'id': 'cp1',
                'ts': 1000,
                'channel_values': {'x': 1},
                'channel_versions': {},
                'versions_seen': {},
            },
            'metadata': {'step': 5},
        }

        mock_client.get_state.side_effect = [
            mock.Mock(data=json.dumps(registry)),
            mock.Mock(data=json.dumps(cp_wrapper)),
        ]

        cp = DaprCheckpointer(self.store, self.prefix)
        lst = cp.list(self.config)

        assert len(lst) == 1
        assert lst[0].checkpoint['id'] == 'cp1'
        assert lst[0].metadata['step'] == 5

    def test_delete_thread_removes_key_and_updates_registry(self, mock_client_cls):
        mock_client = mock_client_cls.return_value

        registry = ['lg:t1']
        mock_client.get_state.return_value.data = json.dumps(registry)

        cp = DaprCheckpointer(self.store, self.prefix)
        cp.delete_thread(self.config)

        mock_client.delete_state.assert_called_once_with(
            store_name='statestore',
            key='lg:t1',
        )

        mock_client.save_state.assert_called_with(
            store_name='statestore',
            key=DaprCheckpointer.REGISTRY_KEY,
            value=json.dumps([]),
        )


if __name__ == '__main__':
    unittest.main()
