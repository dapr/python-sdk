# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation and Dapr Contributors.
Licensed under the MIT License.
"""

import base64
import re
import datetime
import json

from typing import Any, Callable, Optional, Type
from dateutil import parser

from dapr.serializers.base import Serializer
from dapr.serializers.util import (
    convert_from_dapr_duration,
    convert_to_dapr_duration,
    DAPR_DURATION_PARSER
)


class DefaultJSONSerializer(Serializer):
    def serialize(
            self, obj: object,
            custom_hook: Optional[Callable[[object], bytes]] = None) -> bytes:

        dict_obj = obj

        # importing this from top scope creates a circular import
        from dapr.actor.runtime.config import ActorRuntimeConfig
        if callable(custom_hook):
            dict_obj = custom_hook(obj)
        elif isinstance(obj, bytes):
            dict_obj = base64.b64encode(obj).decode('utf-8')
        elif isinstance(obj, ActorRuntimeConfig):
            dict_obj = obj.as_dict()

        serialized = json.dumps(dict_obj, cls=DaprJSONEncoder, separators=(',', ':'))

        return serialized.encode('utf-8')

    def deserialize(
            self, data: bytes, data_type: Optional[Type] = object,
            custom_hook: Optional[Callable[[bytes], object]] = None) -> Any:

        if not isinstance(data, (str, bytes)):
            raise ValueError('data must be str or bytes types')

        obj = json.loads(data, cls=DaprJSONDecoder)

        return custom_hook(obj) if callable(custom_hook) else obj


class DaprJSONEncoder(json.JSONEncoder):
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
        elif isinstance(obj, bytes):
            return base64.b64encode(obj).decode('utf-8')
        else:
            return json.JSONEncoder.default(self, obj)


class DaprJSONDecoder(json.JSONDecoder):
    # TODO: improve regex
    datetime_regex = re.compile(r'(\d{4}[-/]\d{2}[-/]\d{2})')

    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, *args, **kwargs)
        self.parse_string = DaprJSONDecoder.custom_scanstring
        self.scan_once = json.scanner.py_make_scanner(self)  # type: ignore

    @classmethod
    def custom_scanstring(cls, s, end, strict=True):
        (s, end) = json.decoder.scanstring(s, end, strict)  # type: ignore
        if cls.datetime_regex.match(s):
            return (parser.parse(s), end)

        duration = DAPR_DURATION_PARSER.match(s)
        if duration is not None and duration.lastindex is not None:
            return (convert_from_dapr_duration(s), end)
        return (s, end)
