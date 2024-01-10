# -*- coding: utf-8 -*-
# Copyright 2021 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
    print('call actor method via proxy.invoke_method()', flush=True)
    rtn_bytes = await proxy.invoke_method('GetMyData')
    print(rtn_bytes, flush=True)
    # RPC style using python duck-typing
    print('call actor method using rpc style', flush=True)
    rtn_obj = await proxy.GetMyData()
    print(rtn_obj, flush=True)
    # Check actor is reentrant
    is_reentrant = await proxy.invoke_method('GetReentrancyStatus')
    print(f'Actor reentrancy enabled: {str(is_reentrant)}', flush=True)

    # -----------------------------------------------
    # Actor state management demo
    # -----------------------------------------------
    # Invoke SetMyData actor method to save the state
    print('call SetMyData actor method to save the state', flush=True)
    await proxy.SetMyData({'data': 'new_data'})
    # Invoke GetMyData actor method to get the state
    print('call GetMyData actor method to get the state', flush=True)
    rtn_obj = await proxy.GetMyData()
    print(rtn_obj, flush=True)

    # -----------------------------------------------
    # Actor reminder demo
    # -----------------------------------------------
    # Invoke SetReminder actor method to set actor reminder
    print('Register reminder', flush=True)
    await proxy.SetReminder(True)

    # -----------------------------------------------
    # Actor timer demo
    # -----------------------------------------------
    # Invoke SetTimer to set actor timer
    print('Register timer', flush=True)
    await proxy.SetTimer(True)

    # Wait for 30 seconds to see reminder and timer is triggered
    print('waiting for 30 seconds', flush=True)
    await asyncio.sleep(30)

    # Stop reminder and timer
    print('stop reminder', flush=True)
    await proxy.SetReminder(False)
    print('stop timer', flush=True)
    await proxy.SetTimer(False)

    # Clear actor state
    print('clear actor state', flush=True)
    await proxy.ClearMyData()


asyncio.run(main())
