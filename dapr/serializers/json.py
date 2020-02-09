# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import datetime
import decimal
import json
import uuid

from typing import Callable

from dapr.serializers.base import Serializer
from dapr.serializers.util import convert_from_dapr_duration, convert_to_dapr_duration
from dapr.actor.runtime.runtime_config import ActorRuntimeConfig

class DefaultJSONSerializer(Serializer):
    def serialize(
        self, obj: object,
        custom_hook: Callable[[object], dict] = None) -> bytes:

        dict_obj = None
        if callable(custom_hook):
            dict_obj = custom_hook(obj)
        elif isinstance(obj, ActorRuntimeConfig):
            dict_obj = obj.__dict__
        elif isinstance(obj, dict):
            dict_obj = obj    
        else:
            raise ValueError(f'cannot serialize {type(obj)} object')

        serialized = json.dumps(dict_obj, cls=DaprJSONEncoder)

        return serialized.encode('utf-8')

    def deserialize(
        self, data: bytes,
        custom_hook: Callable[[dict], object] = None) -> object:

        data_str = None
        if isinstance(data, str):
            data_str = data.decode()
        elif isinstance(data, bytes):
            data_str = data
        else:
            raise ValueError('data must be str or bytes types')

        obj = json.loads(data_str)

        return custom_hook(obj) if callable(custom_hook) else obj

class DaprJSONEncoder(json.JSONEncoder):
    """
    """
    def default(self, obj):
        # See "Date Time String Format" in the ECMA-262 specification.
        if isinstance(obj, datetime.datetime):
            r = obj.isoformat()
            if obj.microsecond:
                r = r[:23] + r[26:]
            if r.endswith('+00:00'):
                r = r[:-6] + 'Z'
            return r
        elif isinstance(obj, datetime.date):
            return obj.isoformat()
        elif isinstance(obj, datetime.timedelta):
            return convert_to_dapr_duration(obj)
        elif isinstance(obj, (decimal.Decimal, uuid.UUID)):
            return str(obj)
        else:
            return json.JSONEncoder.default(self, obj)
