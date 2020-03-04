# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import asyncio

from flask import current_app, _app_ctx_stack, jsonify, request, abort
from dapr.actor import Actor, ActorRuntime
from dapr.serializers import DefaultJSONSerializer

class DaprActor(object):
    def __init__(self, app=None):
        self.app = app
        self._dapr_serializer = DefaultJSONSerializer()

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._add_actor_config_route(app)
        self._add_actor_activation_route(app)
        self._add_actor_deactivation_route(app)
        self._add_actor_method_route(app)

    def teardown(self, exception):
        # TODO: Deactivate all actors
        pass

    def register_actor(self, actor: Actor) -> None:
        asyncio.run(ActorRuntime.register_actor(actor))

    def _add_actor_config_route(self, app):
        def actor_config_handler():
            serialized = self._dapr_serializer.serialize(ActorRuntime.get_actor_config())
            return serialized, 200
        app.add_url_rule('/dapr/config', None, actor_config_handler, methods=['GET'])
    
    def _add_actor_activation_route(self, app):
        def actor_activation_handler(actor_type_name, actor_id):
            asyncio.run(ActorRuntime.activate(actor_type_name, actor_id))
            return jsonify({'message': '{}.{} actor is activated'.format(actor_type_name, actor_id)}), 200
        app.add_url_rule('/actors/<actor_type_name>/<actor_id>', None, actor_activation_handler, methods=['POST'])
    
    def _add_actor_deactivation_route(self, app):
        def actor_deactivation_handler(actor_type_name, actor_id):
            asyncio.run(ActorRuntime.deactivate(actor_type_name, actor_id))
            return jsonify({'message': '{}.{} actor is deactivated'.format(actor_type_name, actor_id)}), 200
        app.add_url_rule('/actors/<actor_type_name>/<actor_id>', None, actor_deactivation_handler, methods=['DELETE'])
    
    def _add_actor_method_route(self, app):
        def actor_method_handler(actor_type_name, actor_id, method_name):
            # Read raw bytes from request stream
            req_body = request.stream.read()
            result = asyncio.run(ActorRuntime.dispatch(actor_type_name, actor_id, method_name, req_body))
            return result, 200
        app.add_url_rule('/actors/<actor_type_name>/<actor_id>/method/<method_name>', None, actor_method_handler, methods=['PUT'])
