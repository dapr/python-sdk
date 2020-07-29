# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from fastapi import FastAPI
from dapr.ext.fastapi import DaprActor
from demo_actor import DemoActor


app = FastAPI(title=f'{DemoActor.__name__}Service')

# Add Dapr Actor Extension
actor = DaprActor(app)

@app.on_event("startup")
async def startup_event():
    # Register DemoActor
    await actor.register_actor(DemoActor)
