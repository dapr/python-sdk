#!/usr/bin/env python3

"""
Unit tests for the StateItem class.
"""

import unittest

from dapr.clients.grpc._state import StateItem


class TestStateItem(unittest.TestCase):
    """Test cases for StateItem."""

    def test_metadata_defaults_to_empty_dict(self):
        item = StateItem(key='key1', value='value1')
        self.assertEqual(item.metadata, {})

    def test_metadata_not_shared_between_instances(self):
        item1 = StateItem(key='key1', value='value1')
        item2 = StateItem(key='key2', value='value2')

        item1.metadata['injected'] = 'value'

        self.assertNotIn('injected', item2.metadata)

    def test_metadata_uses_provided_value(self):
        item = StateItem(key='key1', value='value1', metadata={'k': 'v'})
        self.assertEqual(item.metadata, {'k': 'v'})


if __name__ == '__main__':
    unittest.main()
