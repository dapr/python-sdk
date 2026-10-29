# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import unittest
from unittest import mock

from flask import Flask

from dapr.actor import ActorRuntime
from dapr.ext.flask import DaprActor


class DaprActorActivationIdTest(unittest.TestCase):
    def setUp(self):
        app = Flask('test_actor_app')
        app.testing = True
        DaprActor(app)
        self.client = app.test_client()

    def test_method_passes_activation_id(self):
        with mock.patch.object(
            ActorRuntime, 'dispatch', new=mock.AsyncMock(return_value=b'"ok"')
        ) as dispatch:
            response = self.client.put(
                '/actors/FakeActor/a1/method/Echo',
                data=b'"hi"',
                headers={'Dapr-Actor-Activation-Id': 'act-1', 'Dapr-Reentrancy-Id': 'rid-1'},
            )

        self.assertEqual(200, response.status_code)
        dispatch.assert_awaited_once_with(
            'FakeActor', 'a1', 'Echo', b'"hi"', 'rid-1', activation_id='act-1'
        )

    def test_method_header_is_case_insensitive(self):
        for header_name in ('dapr-actor-activation-id', 'DAPR-ACTOR-ACTIVATION-ID'):
            with mock.patch.object(
                ActorRuntime, 'dispatch', new=mock.AsyncMock(return_value=b'"ok"')
            ) as dispatch:
                self.client.put(
                    '/actors/FakeActor/a1/method/Echo',
                    data=b'"hi"',
                    headers={header_name: 'act-2'},
                )

            dispatch.assert_awaited_once_with(
                'FakeActor', 'a1', 'Echo', b'"hi"', None, activation_id='act-2'
            )

    def test_method_without_header_passes_none(self):
        with mock.patch.object(
            ActorRuntime, 'dispatch', new=mock.AsyncMock(return_value=b'"ok"')
        ) as dispatch:
            self.client.put('/actors/FakeActor/a1/method/Echo', data=b'"hi"')

        dispatch.assert_awaited_once_with(
            'FakeActor', 'a1', 'Echo', b'"hi"', None, activation_id=None
        )

    def test_timer_passes_activation_id(self):
        with mock.patch.object(ActorRuntime, 'fire_timer', new=mock.AsyncMock()) as fire_timer:
            response = self.client.put(
                '/actors/FakeActor/a1/method/timer/t1',
                data=b'{}',
                headers={'dapr-actor-activation-id': 'act-3'},
            )

        self.assertEqual(200, response.status_code)
        fire_timer.assert_awaited_once_with('FakeActor', 'a1', 't1', b'{}', activation_id='act-3')

    def test_reminder_passes_activation_id(self):
        with mock.patch.object(
            ActorRuntime, 'fire_reminder', new=mock.AsyncMock()
        ) as fire_reminder:
            response = self.client.put(
                '/actors/FakeActor/a1/method/remind/r1',
                data=b'{}',
                headers={'Dapr-Actor-Activation-Id': 'act-4'},
            )

        self.assertEqual(200, response.status_code)
        fire_reminder.assert_awaited_once_with(
            'FakeActor', 'a1', 'r1', b'{}', activation_id='act-4'
        )

    def test_timer_header_is_case_insensitive(self):
        for header_name in ('dapr-actor-activation-id', 'DAPR-ACTOR-ACTIVATION-ID'):
            with mock.patch.object(ActorRuntime, 'fire_timer', new=mock.AsyncMock()) as fire_timer:
                self.client.put(
                    '/actors/FakeActor/a1/method/timer/t1',
                    data=b'{}',
                    headers={header_name: 'act-6'},
                )

            fire_timer.assert_awaited_once_with(
                'FakeActor', 'a1', 't1', b'{}', activation_id='act-6'
            )

    def test_reminder_header_is_case_insensitive(self):
        for header_name in ('dapr-actor-activation-id', 'DAPR-ACTOR-ACTIVATION-ID'):
            with mock.patch.object(
                ActorRuntime, 'fire_reminder', new=mock.AsyncMock()
            ) as fire_reminder:
                self.client.put(
                    '/actors/FakeActor/a1/method/remind/r1',
                    data=b'{}',
                    headers={header_name: 'act-7'},
                )

            fire_reminder.assert_awaited_once_with(
                'FakeActor', 'a1', 'r1', b'{}', activation_id='act-7'
            )

    def test_deactivate_is_unchanged(self):
        with mock.patch.object(ActorRuntime, 'deactivate', new=mock.AsyncMock()) as deactivate:
            response = self.client.delete(
                '/actors/FakeActor/a1', headers={'Dapr-Actor-Activation-Id': 'act-5'}
            )

        self.assertEqual(200, response.status_code)
        deactivate.assert_awaited_once_with('FakeActor', 'a1')


if __name__ == '__main__':
    unittest.main()
