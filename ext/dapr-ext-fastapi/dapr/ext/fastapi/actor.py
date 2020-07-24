# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

# https://github.com/frankie567/fastapi-users/blob/master/fastapi_users/router/users.py

import asyncio
from typing import Any, Optional, Type

from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.responses import JSONResponse

from dapr.actor import Actor, ActorRuntime
from dapr.clients.exceptions import DaprInternalError, ERROR_CODE_UNKNOWN
from dapr.serializers import DefaultJSONSerializer

DEFAULT_CONTENT_TYPE = "application/json; utf-8"


class DaprActor(object):
    def __init__(self, app: FastAPI):
        self._dapr_serializer = DefaultJSONSerializer()
        self._router = APIRouter()
        app.include_router(self._router)

        self.init_routes(self._router)

    def init_routes(self, router: APIRouter):
        @router.get("/healthz")
        async def healthz():
            return {'status': 'ok'}
        
        @router.get('/dapr/config')
        async def dapr_config():
            serialized = self._dapr_serializer.serialize(ActorRuntime.get_actor_config())
            return self.wrap_response(200, serialized)

        @router.delete('/actors/{actor_type_name}/{actor_id}')
        async def actor_deactivation(actor_type_name: str , actor_id: str):
            try:
                await ActorRuntime.deactivate(actor_type_name, actor_id)
            except DaprInternalError as ex:
                return self.wrap_response(500, ex.as_dict())
            except Exception as ex:
                return self.wrap_response(500, repr(ex), ERROR_CODE_UNKNOWN)

            msg = f'deactivated actor: {actor_type_name}.{actor_id}'
            self._app.logger.debug(msg)
            return self.wrap_response(200, msg)

        @router.put('/actors/{actor_type_name}/{actor_id}/method/{method_name}')
        async def actor_method(actor_type_name: str, actor_id: str, method_name: str, request: Request):
            try:
                # Read raw bytes from request stream
                req_body = await request.body()
                result = await ActorRuntime.dispatch(actor_type_name, actor_id, method_name, req_body)
            except DaprInternalError as ex:
                return self.wrap_response(500, ex.as_dict())
            except Exception as ex:
                return self.wrap_response(500, repr(ex), ERROR_CODE_UNKNOWN)

            msg = f'called method. actor: {actor_type_name}.{actor_id}, method: {method_name}'
            self._app.logger.debug(msg)
            return self.wrap_response(200, result)

        @router.put('/actors/<actor_type_name>/<actor_id>/method/timer/<timer_name>')
        async def actor_timer(actor_type_name: str, actor_id: str, timer_name: str):
            try:
                await ActorRuntime.fire_timer(actor_type_name, actor_id, timer_name)
            except DaprInternalError as ex:
                return self.wrap_response(500, ex.as_dict())
            except Exception as ex:
                return self.wrap_response(500, repr(ex), ERROR_CODE_UNKNOWN)

            msg = f'called timer. actor: {actor_type_name}.{actor_id}, timer: {timer_name}'
            # self._app.logger.debug(msg)
            return self.wrap_response(200, msg)

        @router.put('/actors/<actor_type_name>/<actor_id>/method/remind/<reminder_name>')
        async def actor_reminder(actor_type_name: str, actor_id: str, reminder_name: str, request: Request):
            try:
                # Read raw bytes from request stream
                req_body = await request.body()
                await ActorRuntime.fire_reminder(
                    actor_type_name, actor_id, reminder_name, req_body)
            except DaprInternalError as ex:
                return self.wrap_response(500, ex.as_dict())
            except Exception as ex:
                return self.wrap_response(500, repr(ex), ERROR_CODE_UNKNOWN)

            msg = f'called reminder. actor: {actor_type_name}.{actor_id}, reminder: {reminder_name}'
            # self._app.logger.debug(msg)
            return self.wrap_response(200, msg)

    async def register_actor(self, actor: Type[Actor]) -> None:
        await ActorRuntime.register_actor(actor)
        # self._app.logger.debug(f'registered actor: {actor.__class__.__name__}')

    # wrap_response wraps dapr errors to flask response
    def wrap_response(
            self,
            status: int, msg: Any,
            error_code: Optional[str] = None, content_type: Optional[str] = DEFAULT_CONTENT_TYPE):
        resp = None
        if isinstance(msg, str):
            response_obj = {
                'message': msg,
            }
            if not (status >= 200 and status < 300) and error_code:
                response_obj['errorCode'] = error_code
            resp = JSONResponse(content=response_obj, status_code=status)
        elif isinstance(msg, bytes):
            resp = Response(content=msg, media_type=content_type)
        else:
            resp = JSONResponse(content=msg, status_code=status)
        return resp
