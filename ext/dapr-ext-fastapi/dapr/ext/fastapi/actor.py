# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
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

from typing import Any, Optional, Type, List

from fastapi import FastAPI, APIRouter, Request, Response, status   # type: ignore
from fastapi.logger import logger
from fastapi.responses import JSONResponse

from dapr.actor import Actor, ActorRuntime
from dapr.clients.exceptions import DaprInternalError, ERROR_CODE_UNKNOWN
from dapr.serializers import DefaultJSONSerializer

DEFAULT_CONTENT_TYPE = "application/json; utf-8"
DAPR_REENTRANCY_ID_HEADER = 'Dapr-Reentrancy-Id'


def _wrap_response(
        status_code: int,
        msg: Any,
        error_code: Optional[str] = None,
        content_type: Optional[str] = DEFAULT_CONTENT_TYPE):
    resp = None
    if isinstance(msg, str):
        response_obj = {
            'message': msg,
        }
        if not (status_code >= 200 and status_code < 300) and error_code:
            response_obj['errorCode'] = error_code
        resp = JSONResponse(content=response_obj, status_code=status_code)
    elif isinstance(msg, bytes):
        resp = Response(content=msg, media_type=content_type)
    else:
        resp = JSONResponse(content=msg, status_code=status_code)
    return resp


class DaprActor(object):

    def __init__(self, app: FastAPI,
                 router_tags: Optional[List[str]] = ['Actor']):
        # router_tags should be added to all magic Dapr Actor methods implemented here
        self._router_tags = router_tags
        self._router = APIRouter()
        self._dapr_serializer = DefaultJSONSerializer()
        self.init_routes(self._router)
        app.include_router(self._router)

    def init_routes(self, router: APIRouter):
        @router.get("/healthz", tags=self._router_tags)
        async def healthz():
            return {'status': 'ok'}

        @router.get('/dapr/config', tags=self._router_tags)
        async def dapr_config():
            serialized = self._dapr_serializer.serialize(ActorRuntime.get_actor_config())
            return _wrap_response(status.HTTP_200_OK, serialized)

        @router.delete('/actors/{actor_type_name}/{actor_id}', tags=self._router_tags)
        async def actor_deactivation(actor_type_name: str, actor_id: str):
            try:
                await ActorRuntime.deactivate(actor_type_name, actor_id)
            except DaprInternalError as ex:
                return _wrap_response(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    ex.as_dict())
            except Exception as ex:
                return _wrap_response(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    repr(ex),
                    ERROR_CODE_UNKNOWN)

            msg = f'deactivated actor: {actor_type_name}.{actor_id}'
            logger.debug(msg)
            return _wrap_response(status.HTTP_200_OK, msg)

        @router.put('/actors/{actor_type_name}/{actor_id}/method/{method_name}',
                    tags=self._router_tags)
        async def actor_method(
                actor_type_name: str,
                actor_id: str,
                method_name: str,
                request: Request):
            try:
                # Read raw bytes from request stream
                req_body = await request.body()
                reentrancy_id = request.headers.get(DAPR_REENTRANCY_ID_HEADER)
                result = await ActorRuntime.dispatch(
                    actor_type_name, actor_id, method_name, req_body, reentrancy_id)
            except DaprInternalError as ex:
                return _wrap_response(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, ex.as_dict())
            except Exception as ex:
                return _wrap_response(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    repr(ex),
                    ERROR_CODE_UNKNOWN)

            msg = f'called method. actor: {actor_type_name}.{actor_id}, method: {method_name}'
            logger.debug(msg)
            return _wrap_response(status.HTTP_200_OK, result)

        @router.put('/actors/{actor_type_name}/{actor_id}/method/timer/{timer_name}',
                    tags=self._router_tags)
        async def actor_timer(
                actor_type_name: str,
                actor_id: str,
                timer_name: str,
                request: Request):
            try:
                # Read raw bytes from request stream
                req_body = await request.body()
                await ActorRuntime.fire_timer(actor_type_name, actor_id, timer_name, req_body)
            except DaprInternalError as ex:
                return _wrap_response(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    ex.as_dict())
            except Exception as ex:
                return _wrap_response(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    repr(ex),
                    ERROR_CODE_UNKNOWN)

            msg = f'called timer. actor: {actor_type_name}.{actor_id}, timer: {timer_name}'
            logger.debug(msg)
            return _wrap_response(status.HTTP_200_OK, msg)

        @router.put('/actors/{actor_type_name}/{actor_id}/method/remind/{reminder_name}',
                    tags=self._router_tags)
        async def actor_reminder(
                actor_type_name: str,
                actor_id: str,
                reminder_name: str,
                request: Request):
            try:
                # Read raw bytes from request stream
                req_body = await request.body()
                await ActorRuntime.fire_reminder(
                    actor_type_name, actor_id, reminder_name, req_body)
            except DaprInternalError as ex:
                return _wrap_response(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    ex.as_dict())
            except Exception as ex:
                return _wrap_response(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    repr(ex),
                    ERROR_CODE_UNKNOWN)

            msg = f'called reminder. actor: {actor_type_name}.{actor_id}, reminder: {reminder_name}'
            logger.debug(msg)
            return _wrap_response(status.HTTP_200_OK, msg)

    async def register_actor(self, actor: Type[Actor]) -> None:
        await ActorRuntime.register_actor(actor)
        logger.debug(f'registered actor: {actor.__class__.__name__}')
