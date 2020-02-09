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
from dapr.actor import ActorRuntimeConfig

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

        obj = json.loads(data_str, cls=DaprJSONDecoder)

        return custom_hook(obj) if callable(custom_hook) else obj

class DaprJSONEncoder(json.JSONEncoder):
    def default(self, o):
        # See "Date Time String Format" in the ECMA-262 specification.
        if isinstance(o, datetime.datetime):
            r = o.isoformat()
            if o.microsecond:
                r = r[:23] + r[26:]
            if r.endswith('+00:00'):
                r = r[:-6] + 'Z'
            return r
        elif isinstance(o, datetime.date):
            return o.isoformat()
        elif isinstance(o, datetime.timedelta):
            return convert_to_dapr_duration(o)
        elif isinstance(o, (decimal.Decimal, uuid.UUID)):
            return str(o)
        else:
            return super().default(o)

class DaprJSONDecoder(json.JSONDecoder):
    def default(self, o):
        # See "Date Time String Format" in the ECMA-262 specification.
        if isinstance(o, datetime.datetime):
            r = o.isoformat()
            if o.microsecond:
                r = r[:23] + r[26:]
            if r.endswith('+00:00'):
                r = r[:-6] + 'Z'
            return r
        elif isinstance(o, datetime.date):
            return o.isoformat()
        elif isinstance(o, datetime.timedelta):
            return convert_to_dapr_duration(o)
        elif isinstance(o, (decimal.Decimal, uuid.UUID)):
            return str(o)
        else:
            return super().default(o)