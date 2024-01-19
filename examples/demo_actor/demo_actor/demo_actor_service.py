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

from fastapi import FastAPI  # type: ignore
from dapr.actor.runtime.config import ActorRuntimeConfig, ActorTypeConfig, ActorReentrancyConfig
from dapr.actor.runtime.runtime import ActorRuntime
from dapr.ext.fastapi import DaprActor  # type: ignore
from demo_actor import DemoActor


app = FastAPI(title=f'{DemoActor.__name__}Service')

# This is an optional advanced configuration which enables reentrancy only for the
# specified actor type. By default reentrancy is not enabled for all actor types.
config = ActorRuntimeConfig()  # init with default values
config.update_actor_type_configs(
    [ActorTypeConfig(actor_type=DemoActor.__name__, reentrancy=ActorReentrancyConfig(enabled=True))]
)
ActorRuntime.set_actor_config(config)

# Add Dapr Actor Extension
actor = DaprActor(app)


@app.on_event('startup')
async def startup_event():
    # Register DemoActor
    await actor.register_actor(DemoActor)
