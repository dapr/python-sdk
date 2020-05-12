# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio

from dapr.actor import ActorProxy, ActorId
from examples.demo_actor.demo_actor_interface import DemoActorInterface


async def main():
    # Create proxy client
    proxy = ActorProxy.create(DemoActorInterface, 'DemoActor', ActorId('1'))

    # -----------------------------------------------
    # Actor invocation demo
    # -----------------------------------------------
    # non-remoting actor invocation
    rtn_bytes = await proxy.invoke("GetMyData")
    print(rtn_bytes, flush=True)
    # RPC style using python duck-typing
    rtn_obj = await proxy.GetMyData()
    print(rtn_obj, flush=True)

    # -----------------------------------------------
    # Actor state management demo
    # -----------------------------------------------
    # Invoke SetMyData actor method to save the state
    await proxy.SetMyData({'data': 'new_data'})
    # Invoke GetMyData actor method to get the state
    rtn_obj = await proxy.GetMyData()
    print(rtn_obj, flush=True)

    # -----------------------------------------------
    # Actor reminder demo
    # -----------------------------------------------
    # Invoke SetReminder actor method to set actor reminder
    print("set reminder", flush=True)
    await proxy.SetReminder(True)

    # -----------------------------------------------
    # Actor timer demo
    # -----------------------------------------------
    # Invoke SetTimer to set actor timer
    print("set timer", flush=True)
    await proxy.SetTimer(True)

    # Wait for 30 seconds to see reminder and timer is triggered
    print("waiting for 30 seconds", flush=True)
    await asyncio.sleep(30)

    # Stop reminder and timer
    print("stop reminder", flush=True)
    await proxy.SetReminder(False)
    print("stop timer", flush=True)
    await proxy.SetTimer(False)


asyncio.run(main())
