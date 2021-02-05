# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation and Dapr Contributors.
# Licensed under the MIT License.

from fastapi import FastAPI  # type: ignore
from dapr.ext.fastapi import DaprActor  # type: ignore
from demo_actor import DemoActor


app = FastAPI(title=f'{DemoActor.__name__}Service')

# Add Dapr Actor Extension
actor = DaprActor(app)

@app.on_event("startup")
async def startup_event():
    # Register DemoActor
    await actor.register_actor(DemoActor)
