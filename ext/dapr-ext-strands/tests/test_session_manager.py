# -*- coding: utf-8 -*-

import unittest
from unittest import mock
import json
import time

from strands.types.session import Session, SessionAgent, SessionMessage
from strands.types.exceptions import SessionException

from dapr.ext.strands.dapr_session_manager import DaprSessionManager


def dapr_state(data):
    """Simulate a real Dapr get_state() response."""
    resp = mock.Mock()
    resp.data = None if data is None else json.dumps(data).encode("utf-8")
    return resp


def make_session(session_id="s1"):
    return Session.from_dict(
        {
            "session_id": session_id,
            "session_type": "chat",
            "created_at": time.time(),
            "metadata": {},
        }
    )


def make_agent(agent_id="a1"):
    return SessionAgent.from_dict(
        {
            "agent_id": agent_id,
            "state": {},
            "conversation_manager_state": {},
            "created_at": time.time(),
        }
    )


def make_message(message_id=1, text="hello"):
    return SessionMessage.from_dict(
        {
            "message_id": message_id,
            "role": "user",
            "message": text,
            "created_at": time.time(),
        }
    )


@mock.patch("dapr.ext.strands.dapr_session_manager.DaprClient")
class DaprSessionManagerTest(unittest.TestCase):

    def setUp(self):
        self.session_id = "s1"
        self.store = "statestore"

        self.mock_client = mock.Mock()
        self.mock_client.get_state.return_value = dapr_state(None)

        self.manager = DaprSessionManager(
            session_id=self.session_id,
            state_store_name=self.store,
            dapr_client=self.mock_client,
        )

    #
    # session
    #
    def test_create_and_read_session(self, _):
        session = make_session(self.session_id)

        self.manager.create_session(session)

        self.mock_client.get_state.return_value = dapr_state(session.to_dict())
        read = self.manager.read_session(self.session_id)

        assert read.session_id == self.session_id

    def test_create_session_raises_if_exists(self, _):
        session = make_session(self.session_id)

        self.mock_client.get_state.return_value = dapr_state(session.to_dict())

        with self.assertRaises(SessionException):
            self.manager.create_session(session)

    #
    # agent
    #
    def test_create_and_read_agent(self, _):
        agent = make_agent("a1")

        self.manager.create_agent(self.session_id, agent)

        self.mock_client.get_state.return_value = dapr_state(agent.to_dict())
        read = self.manager.read_agent(self.session_id, "a1")

        assert read.agent_id == "a1"

    def test_update_agent_preserves_created_at(self, _):
        agent = make_agent("a1")
        original_ts = agent.created_at

        self.mock_client.get_state.return_value = dapr_state(agent.to_dict())

        agent.state["x"] = 1
        self.manager.update_agent(self.session_id, agent)

        saved = json.loads(self.mock_client.save_state.call_args[1]["value"])
        assert saved["created_at"] == original_ts


    def test_create_and_read_message(self, _):
        msg = make_message(1, "hello")

        self.manager.create_message(self.session_id, "a1", msg)

        messages = {"messages": [msg.to_dict()]}
        self.mock_client.get_state.return_value = dapr_state(messages)

        read = self.manager.read_message(self.session_id, "a1", 1)
        assert read.message == "hello"

    def test_update_message_preserves_created_at(self, _):
        msg = make_message(1, "old")
        original_ts = msg.created_at

        messages = {"messages": [msg.to_dict()]}
        self.mock_client.get_state.return_value = dapr_state(messages)

        msg.message = "new"
        self.manager.update_message(self.session_id, "a1", msg)

        saved = json.loads(self.mock_client.save_state.call_args[1]["value"])
        updated = saved["messages"][0]

        assert updated["created_at"] == original_ts
        assert updated["message"] == "new"


    def test_delete_session_deletes_agents_and_messages(self, _):
        manifest = {"agents": ["a1", "a2"]}
        self.mock_client.get_state.return_value = dapr_state(manifest)

        self.manager.delete_session(self.session_id)
        assert self.mock_client.delete_state.call_count == 6

    def test_close_only_closes_owned_client(self, _):
        self.manager._owns_client = True
        self.manager.close()
        self.mock_client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
