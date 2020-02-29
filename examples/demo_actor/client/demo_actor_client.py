# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio

from dapr.actor import ActorProxy, ActorId
from examples.demo_actor.demo_actor_interface import DemoActorInterface

async def client_main():
    proxy = ActorProxy.create(DemoActorInterface, 'DemoActor', ActorId('1'))
    my_data = await proxy.GetMyData()
    print(my_data, flush=True)

asyncio.run(client_main())