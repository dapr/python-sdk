# -*- coding: utf-8 -*-

import json
import unittest
from datetime import datetime
from unittest import mock

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
        cp.put(self.config, self.checkpoint, None, {'step': 10})

        first_call = mock_client.save_state.call_args_list[0][0]
        assert first_call[0] == 'statestore'
        assert first_call[1] == 'lg:t1'
        saved_payload = json.loads(first_call[2])
        assert saved_payload['metadata']['step'] == 10

        second_call = mock_client.save_state.call_args_list[1][0]
        assert second_call[0] == 'statestore'
        assert second_call[1] == DaprCheckpointer.REGISTRY_KEY

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
        call = mock_client.save_state.call_args[0]
        saved = json.loads(call[2])
        assert saved['checkpoint']['channel_values']['a'] == 99

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
