# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json

from dapr.serializers.base import Serializer

class DefaultJSONSerializer(Serializer):
    def __init__(self):
        pass

    def serialize(self, data: object) -> str:
        return json.dumps(data)

    def deserialize(self, data: bytes) -> object:
        if not isinstance(data, bytes):
            data = data.decode()

        return json.loads(data)


"""
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
        elif isinstance(o, (decimal.Decimal, uuid.UUID)):
            return str(o)
        else:
            return super().default(o)
"""