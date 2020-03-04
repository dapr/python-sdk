# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio

from dapr.actor import ActorProxy, ActorId
from examples.demo_actor.demo_actor_interface import DemoActorInterface

async def main():
    proxy = ActorProxy.create(DemoActorInterface, 'DemoActor', ActorId('1'))

    rtn_bytes = await proxy.invoke("GetMyData")
    print(rtn_bytes, flush=True)
    rtn_obj = await proxy.GetMyData()
    print(rtn_obj, flush=True)

    await proxy.SetMyData({'data': 'new_data'})
    rtn_obj = await proxy.GetMyData()
    print(rtn_obj, flush=True)

asyncio.run(main())