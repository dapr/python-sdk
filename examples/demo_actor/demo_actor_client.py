# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio

from dapr.actor import ActorProxy, ActorId
from demo_actor_interface import DemoActorInterface


async def main():
    # Create proxy client
    proxy = ActorProxy.create('DemoActor', ActorId('1'), DemoActorInterface)

    # -----------------------------------------------
    # Actor invocation demo
    # -----------------------------------------------
    # non-remoting actor invocation
    print("call actor method via proxy.invoke()", flush=True)
    rtn_bytes = await proxy.invoke("GetMyData")
    print(rtn_bytes, flush=True)
    # RPC style using python duck-typing
    print("call actor method using rpc style", flush=True)
    rtn_obj = await proxy.GetMyData()
    print(rtn_obj, flush=True)

    # -----------------------------------------------
    # Actor state management demo
    # -----------------------------------------------
    # Invoke SetMyData actor method to save the state
    print("call SetMyData actor method to save the state", flush=True)
    await proxy.SetMyData({'data': 'new_data'})
    # Invoke GetMyData actor method to get the state
    print("call GetMyData actor method to get the state", flush=True)
    rtn_obj = await proxy.GetMyData()
    print(rtn_obj, flush=True)

    # -----------------------------------------------
    # Actor reminder demo
    # -----------------------------------------------
    # Invoke SetReminder actor method to set actor reminder
    print("Register reminder", flush=True)
    await proxy.SetReminder(True)

    # -----------------------------------------------
    # Actor timer demo
    # -----------------------------------------------
    # Invoke SetTimer to set actor timer
    print("Register timer", flush=True)
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
