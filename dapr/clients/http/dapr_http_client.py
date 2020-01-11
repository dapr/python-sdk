from dapr.clients import DaprClientBase
from dapr.conf import settings
import requests
import json

class DaprHttpClient(DaprClientBase):
    def __init__(self, settings = None):
        self._settings = settings
        self._session = requests.Session()

    def invoke_actor_method(self, actor_type, actor_id, method, data):
        url = 'http://localhost:{}/{}/actors/{}/{}/method/{}'.format(
            settings.DAPR_HTTP_PORT,
            settings.DAPR_API_VERSION,
            actor_type,
            actor_id,
            method)

        body_bytes = b'' if data is None else json.dumps(data)
        req = requests.Request(method='POST', url=url, data=body_bytes)
        prepped = req.prepare()
        prepped.headers['Content-Type'] = 'application/json'
        resp = self._session.send(prepped)

        return resp.json()