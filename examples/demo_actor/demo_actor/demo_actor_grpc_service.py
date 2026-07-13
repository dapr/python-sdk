# -*- coding: utf-8 -*-
# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""DemoActor hosted over the Dapr gRPC actor stream (alpha).

Unlike demo_actor_service.py (FastAPI) and demo_actor_flask.py (Flask), this
service exposes no actor callback endpoints and writes no server boilerplate:
ActorGrpcHost dials daprd's gRPC port, receives all actor callbacks
(invocations, reminders, timers, deactivations) over a single app-initiated
stream, and manages the minimal app-channel listener daprd requires (on the
port from the APP_PORT env var that `dapr run` sets).

Run with:
    dapr run --app-id demo-actor --app-port 3000 --app-protocol grpc -- \
        python3 demo_actor_grpc_service.py
"""

import asyncio

from demo_actor import DemoActor

from dapr.actor import ActorGrpcHost
from dapr.actor.runtime.config import ActorReentrancyConfig, ActorRuntimeConfig, ActorTypeConfig
from dapr.actor.runtime.runtime import ActorRuntime


async def main() -> None:
    # This is an optional advanced configuration which enables reentrancy only for the
    # specified actor type. By default reentrancy is not enabled for all actor types.
    config = ActorRuntimeConfig()  # init with default values
    config.update_actor_type_configs(
        [
            ActorTypeConfig(
                actor_type=DemoActor.__name__, reentrancy=ActorReentrancyConfig(enabled=True)
            )
        ]
    )
    ActorRuntime.set_actor_config(config)

    host = ActorGrpcHost()
    await host.register_actor(DemoActor)
    print(f'{DemoActor.__name__} is hosted over the Dapr gRPC actor stream', flush=True)
    await host.run_forever()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
