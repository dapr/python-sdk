# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import asyncio

from flask import jsonify, request
from dapr.actor import Actor, ActorRuntime
from dapr.serializers import DefaultJSONSerializer


class DaprActor(object):
    def __init__(self, app=None):
        self.app = app
        self._dapr_serializer = DefaultJSONSerializer()

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._add_healthz(app)
        self._add_actor_config_route(app)
        self._add_actor_activation_route(app)
        self._add_actor_deactivation_route(app)
        self._add_actor_method_route(app)

    def teardown(self, exception):
        # TODO: Deactivate all actors
        pass

    def register_actor(self, actor: Actor) -> None:
        asyncio.run(ActorRuntime.register_actor(actor))

    def _add_healthz(self, app):
        def actor_health_handler():
            return '', 200
        app.add_url_rule(
            '/healthz', None,
            actor_health_handler,
            methods=['GET'])

    def _add_actor_config_route(self, app):
        def actor_config_handler():
            serialized = self._dapr_serializer.serialize(ActorRuntime.get_actor_config())
            return serialized, 200
        app.add_url_rule(
            '/dapr/config', None,
            actor_config_handler,
            methods=['GET'])

    def _add_actor_activation_route(self, app):
        def actor_activation_handler(actor_type_name, actor_id):
            asyncio.run(ActorRuntime.activate(actor_type_name, actor_id))
            return jsonify({'message': f'{actor_type_name}.{actor_id} actor is activated'}), 200

        app.add_url_rule(
            '/actors/<actor_type_name>/<actor_id>', None,
            actor_activation_handler,
            methods=['POST'])

    def _add_actor_deactivation_route(self, app):
        def actor_deactivation_handler(actor_type_name, actor_id):
            asyncio.run(ActorRuntime.deactivate(actor_type_name, actor_id))
            return jsonify({'message': f'{actor_type_name}.{actor_id} actor is deactivated'}), 200

        app.add_url_rule(
            '/actors/<actor_type_name>/<actor_id>', None,
            actor_deactivation_handler,
            methods=['DELETE'])

    def _add_actor_method_route(self, app):
        def actor_method_handler(actor_type_name, actor_id, method_name):
            # Read raw bytes from request stream
            req_body = request.stream.read()
            try:
                result = asyncio.run(ActorRuntime.dispatch(
                    actor_type_name, actor_id, method_name, req_body))
            except Exception as ex:
                # TODO: Better error handling
                dapr_error = {
                    'message': str(ex)
                }
                return dapr_error, 500
            return result, 200
        app.add_url_rule(
            '/actors/<actor_type_name>/<actor_id>/method/<method_name>',
            None, actor_method_handler,
            methods=['PUT'])

    def _add_timer_route(self, app):
        def actor_timer_handler(actor_type_name, actor_id, timer_name):
            # Read raw bytes from request stream
            req_body = request.stream.read()
            try:
                result = asyncio.run(ActorRuntime.fire_timer(actor_type_name, actor_id, timer_name))
            except Exception as ex:
                # TODO: Better error handling
                dapr_error = {
                    'message': str(ex)
                }
                return dapr_error, 500
            return result, 200
        app.add_url_rule(
            '/actors/<actor_type_name>/<actor_id>/method/timer/<timer_name>',
            None, actor_timer_handler, methods=['PUT'])

    def _add_reminder_route(self, app):
        def actor_reminder_handler(actor_type_name, actor_id, reminder_name):
            # Read raw bytes from request stream
            req_body = request.stream.read()
            try:
                result = asyncio.run(ActorRuntime.fire_reminder(actor_type_name, actor_id, reminder_name, req_body))
            except Exception as ex:
                # TODO: Better error handling
                dapr_error = {
                    'message': str(ex)
                }
                return dapr_error, 500
            return result, 200
        app.add_url_rule(
            '/actors/<actor_type_name>/<actor_id>/method/remind/<reminder_name>',
            None, actor_reminder_handler, methods=['PUT'])
