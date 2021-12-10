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

from dapr.actor import ActorInterface, actormethod


class DemoActorInterface(ActorInterface):
    @actormethod(name="GetMyData")
    async def get_my_data(self) -> object:
        ...

    @actormethod(name="SetMyData")
    async def set_my_data(self, data: object) -> None:
        ...

    @actormethod(name="SetReminder")
    async def set_reminder(self, enabled: bool) -> None:
        ...

    @actormethod(name="SetTimer")
    async def set_timer(self, enabled: bool) -> None:
        ...
