# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
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

from dapr.actor.runtime._type_information import ActorTypeInformation
from tests.actor.fake_actor_classes import (
    FakeActorCls1Interface,
    FakeActorCls2Interface,
    FakeMultiInterfacesActor,
    FakeSimpleActor,
    ReentrantActorInterface,
)


class ActorTypeInformationTests(unittest.TestCase):
    def setUp(self):
        pass

    def test_actor_type_name(self):
        type_info = ActorTypeInformation.create(FakeSimpleActor)
        self.assertEqual(FakeSimpleActor.__name__, type_info.type_name)

    def test_implementation_type_returns_correct_type(self):
        type_info = ActorTypeInformation.create(FakeSimpleActor)
        self.assertEqual(FakeSimpleActor, type_info.implementation_type)

    def test_actor_interfaces_returns_actor_classes(self):
        type_info = ActorTypeInformation.create(FakeMultiInterfacesActor)

        self.assertEqual(FakeMultiInterfacesActor.__name__, type_info.type_name)
        self.assertEqual(3, len(type_info.actor_interfaces))
        self.assertTrue(type_info.actor_interfaces.index(FakeActorCls1Interface) >= 0)
        self.assertTrue(type_info.actor_interfaces.index(FakeActorCls2Interface) >= 0)
        self.assertTrue(type_info.actor_interfaces.index(ReentrantActorInterface) >= 0)
