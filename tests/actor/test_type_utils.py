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

from dapr.actor.actor_interface import ActorInterface
from dapr.actor.runtime._type_utils import (
    get_class_method_args,
    get_method_arg_types,
    get_method_return_types,
    is_dapr_actor,
    get_actor_interfaces,
    get_dispatchable_attrs,
)

from tests.actor.fake_actor_classes import (
    FakeSimpleActor,
    FakeMultiInterfacesActor,
    FakeActorCls1Interface,
    FakeActorCls2Interface,
)


class TypeUtilsTests(unittest.TestCase):
    def test_get_class_method_args(self):
        args = get_class_method_args(FakeSimpleActor.actor_method)
        self.assertEqual(args, ['arg'])

    def test_get_method_arg_types(self):
        arg_types = get_method_arg_types(FakeSimpleActor.non_actor_method)
        self.assertEqual(arg_types, [type(int(30)), type(str('102')), type(float(10.0))])

    def test_get_return_types(self):
        rtn_type = get_method_return_types(FakeSimpleActor.actor_method)
        self.assertEqual(dict, rtn_type)

        rtn_type = get_method_return_types(FakeSimpleActor.non_actor_method)
        self.assertEqual(str, rtn_type)

    def test_is_dapr_actor_true(self):
        self.assertTrue(is_dapr_actor(FakeSimpleActor))

    def test_is_dapr_actor_false(self):
        # Non-actor class
        class TestNonActorClass(ActorInterface):
            def test_method(self, arg: int) -> object:
                pass

        self.assertFalse(is_dapr_actor(TestNonActorClass))

    def test_get_actor_interface(self):
        actor_interfaces = get_actor_interfaces(FakeMultiInterfacesActor)

        self.assertEqual(FakeActorCls1Interface, actor_interfaces[0])
        self.assertEqual(FakeActorCls2Interface, actor_interfaces[1])

    def test_get_dispatchable_attrs(self):
        dispatchable_attrs = get_dispatchable_attrs(FakeMultiInterfacesActor)
        expected_dispatchable_attrs = [
            'ActorCls1Method',
            'ActorCls1Method1',
            'ActorCls1Method2',
            'ActorCls2Method',
        ]

        method_cnt = 0
        for method in expected_dispatchable_attrs:
            if dispatchable_attrs.get(method) is not None:
                method_cnt = method_cnt + 1

        self.assertEqual(len(expected_dispatchable_attrs), method_cnt)
