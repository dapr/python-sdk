# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import asyncio
from typing import Any, Optional, Type

from flask import jsonify, make_response, request

from dapr.actor import Actor, ActorRuntime
from dapr.clients.exceptions import DaprInternalError, ERROR_CODE_UNKNOWN
from dapr.serializers import DefaultJSONSerializer

DEFAULT_CONTENT_TYPE = 'application/json; utf-8'
DAPR_REENTRANCY_ID_HEADER = 'Dapr-Reentrancy-Id'


class DaprActor(object):
    def __init__(self, app=None):
        self._app = app
        self._dapr_serializer = DefaultJSONSerializer()

        if app is not None:
            self.init_routes(app)

    def init_routes(self, app):
        app.add_url_rule('/healthz', None, self._healthz_handler, methods=['GET'])
        app.add_url_rule('/dapr/config', None, self._config_handler, methods=['GET'])
        app.add_url_rule(
            '/actors/<actor_type_name>/<actor_id>',
            None,
            self._deactivation_handler,
            methods=['DELETE'],
        )
        app.add_url_rule(
            '/actors/<actor_type_name>/<actor_id>/method/<method_name>',
            None,
            self._method_handler,
            methods=['PUT'],
        )
        app.add_url_rule(
            '/actors/<actor_type_name>/<actor_id>/method/timer/<timer_name>',
            None,
            self._timer_handler,
            methods=['PUT'],
        )
        app.add_url_rule(
            '/actors/<actor_type_name>/<actor_id>/method/remind/<reminder_name>',
            None,
            self._reminder_handler,
            methods=['PUT'],
        )

    def teardown(self, exception):
        self._app.logger.debug('actor service is shutting down.')

    def register_actor(self, actor: Type[Actor], **kwargs) -> None:
        asyncio.run(ActorRuntime.register_actor(actor, **kwargs))
        self._app.logger.debug(f'registered actor: {actor.__class__.__name__}')

    def _healthz_handler(self):
        return wrap_response(200, 'ok')

    def _config_handler(self):
        serialized = self._dapr_serializer.serialize(ActorRuntime.get_actor_config())
        return wrap_response(200, serialized)

    def _deactivation_handler(self, actor_type_name, actor_id):
        try:
            asyncio.run(ActorRuntime.deactivate(actor_type_name, actor_id))
        except DaprInternalError as ex:
            return wrap_response(500, ex.as_dict())
        except Exception as ex:
            return wrap_response(500, repr(ex), ERROR_CODE_UNKNOWN)

        msg = f'deactivated actor: {actor_type_name}.{actor_id}'
        self._app.logger.debug(msg)
        return wrap_response(200, msg)

    def _method_handler(self, actor_type_name, actor_id, method_name):
        try:
            # Read raw bytes from request stream
            req_body = request.stream.read()
            reentrancy_id = request.headers.get(DAPR_REENTRANCY_ID_HEADER)
            result = asyncio.run(
                ActorRuntime.dispatch(
                    actor_type_name, actor_id, method_name, req_body, reentrancy_id
                )
            )
        except DaprInternalError as ex:
            return wrap_response(500, ex.as_dict())
        except Exception as ex:
            return wrap_response(500, repr(ex), ERROR_CODE_UNKNOWN)

        msg = f'called method. actor: {actor_type_name}.{actor_id}, method: {method_name}'
        self._app.logger.debug(msg)
        return wrap_response(200, result)

    def _timer_handler(self, actor_type_name, actor_id, timer_name):
        try:
            # Read raw bytes from request stream
            req_body = request.stream.read()
            asyncio.run(ActorRuntime.fire_timer(actor_type_name, actor_id, timer_name, req_body))
        except DaprInternalError as ex:
            return wrap_response(500, ex.as_dict())
        except Exception as ex:
            return wrap_response(500, repr(ex), ERROR_CODE_UNKNOWN)

        msg = f'called timer. actor: {actor_type_name}.{actor_id}, timer: {timer_name}'
        self._app.logger.debug(msg)
        return wrap_response(200, msg)

    def _reminder_handler(self, actor_type_name, actor_id, reminder_name):
        try:
            # Read raw bytes from request stream
            req_body = request.stream.read()
            asyncio.run(
                ActorRuntime.fire_reminder(actor_type_name, actor_id, reminder_name, req_body)
            )
        except DaprInternalError as ex:
            return wrap_response(500, ex.as_dict())
        except Exception as ex:
            return wrap_response(500, repr(ex), ERROR_CODE_UNKNOWN)

        msg = f'called reminder. actor: {actor_type_name}.{actor_id}, reminder: {reminder_name}'
        self._app.logger.debug(msg)
        return wrap_response(200, msg)


# wrap_response wraps dapr errors to flask response
def wrap_response(
    status: int, msg: Any, error_code: Optional[str] = None, content_type: Optional[str] = None
):
    resp = None
    if isinstance(msg, str):
        response_obj = {
            'message': msg,
        }
        if not (status >= 200 and status < 300) and error_code:
            response_obj['errorCode'] = error_code
        resp = make_response(jsonify(response_obj), status)
    elif isinstance(msg, bytes):
        resp = make_response(msg, status)
    else:
        resp = make_response(jsonify(msg), status)
    resp.headers['Content-type'] = content_type or DEFAULT_CONTENT_TYPE
    return resp
