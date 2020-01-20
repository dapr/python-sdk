# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from flask import Flask, jsonify
from flask_dapr.actor import DaprActor
from dapr.conf import settings
from examples.demo_actor.service.demo_actor import DemoActor

app = Flask('DemoActorService')
actor = DaprActor(app)

# register DemoActor
actor.actor_runtime.register_actor(DemoActor)

@app.route('/')
def index():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(port=settings.HTTP_APP_PORT)