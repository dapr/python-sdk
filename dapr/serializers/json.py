# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import re
import datetime
import json

from typing import Callable

from dapr.serializers.base import Serializer
from dapr.serializers.util import convert_from_dapr_duration, convert_to_dapr_duration, DAPR_DURATION_PARSER
from dapr.actor.runtime.runtime_config import ActorRuntimeConfig

class DefaultJSONSerializer(Serializer):
    def serialize(
        self, obj: object,
        custom_hook: Callable[[object], dict]=None) -> bytes:

        dict_obj = None
        if callable(custom_hook):
            dict_obj = custom_hook(obj)
        elif isinstance(obj, ActorRuntimeConfig):
            dict_obj = obj.__dict__
        elif isinstance(obj, dict):
            dict_obj = obj    
        else:
            raise ValueError(f'cannot serialize {type(obj)} object')

        serialized = json.dumps(dict_obj, cls=DaprJSONEncoder, separators=(',', ':'))

        return serialized.encode('utf-8')

    def deserialize(
        self, data: bytes,
        custom_hook: Callable[[dict], object]=None) -> object:

        if not isinstance(data, (str, bytes)):
            raise ValueError('data must be str or bytes types')

        obj = json.loads(data, cls=DaprJSONDecoder)

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
        else:
            return json.JSONEncoder.default(self, obj)

class DaprJSONDecoder(json.JSONDecoder):
    # TODO: improve regex
    datetime_regex = re.compile(r'(\d{4}[-/]\d{2}[-/]\d{2})')

    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, *args, **kwargs)
        self.parse_string = DaprJSONDecoder.custom_scanstring
        self.scan_once = json.scanner.py_make_scanner(self) 

    @classmethod
    def custom_scanstring(cls, s, end, strict=True):
        (s, end) = json.decoder.scanstring(s, end, strict)
        if cls.datetime_regex.match(s):
            return (datetime.datetime.fromisoformat(s), end)
        
        duration = DAPR_DURATION_PARSER.match(s)
        if duration.lastindex is not None:
            return (convert_from_dapr_duration(s), end)
        else:
            return (s, end)
