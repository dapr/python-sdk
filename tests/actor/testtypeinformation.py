# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import unittest

from datetime import timedelta
from dapr.actor.runtime.typeinformation import ActorTypeInformation

from .fakeactorclasses import *


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
        self.assertEqual(2, len(type_info.actor_interfaces))
        self.assertTrue(type_info.actor_interfaces.index(FakeActorCls1Interface) >= 0)
        self.assertTrue(type_info.actor_interfaces.index(FakeActorCls2Interface) >= 0)
