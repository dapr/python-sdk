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

    print("set reminder", flush=True)
    await proxy.SetReminder(True)
    print("set timer", flush=True)
    await proxy.SetTimer(True)

    print("waiting for 30 seconds", flush=True)
    await asyncio.sleep(30)

    print("stop reminder", flush=True)
    await proxy.SetReminder(False)
    print("stop timer", flush=True)
    await proxy.SetTimer(False)


asyncio.run(main())
