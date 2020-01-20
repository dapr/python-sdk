# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dapr.actor import DaprActorClientBase, DaprActorReminder, DaprActorTimer, DaprActorStateTransaction
from dapr.conf import settings

import requests
import json

class DaprActorHttpClient(DaprActorClientBase):

    def __init__(self, settings = None):
        self._settings = settings
        self._session = requests.Session()

    def _get_base_url(self, actor_type, actor_id) -> str:
        return 'http://localhost:{}/{}/actors/{}/{}'.format(
            settings.DAPR_HTTP_PORT,
            settings.DAPR_API_VERSION,
            actor_type,
            actor_id)

    def invoke_method(self, actor_type, actor_id, method, data) -> object:
        url = '{}/method/{}'.format(
            self._get_base_url(actor_type, actor_id),
            method)

        body_bytes = b'' if data is None else json.dumps(data)
        req = requests.Request(method='POST', url=url, data=body_bytes)
        prepped = req.prepare()
        prepped.headers['Content-Type'] = 'application/json'
        resp = self._session.send(prepped)

        return resp.json()
    
    def save_state(self, actor_type, actor_id, key, data) -> None:
        url = '{}/state/{}'.format(
            self._get_base_url(actor_type, actor_id),
            key)

        body_bytes = b'' if data is None else json.dumps(data)
        req = requests.Request(method='PUT', url=url, data=body_bytes)
        prepped = req.prepare()
        prepped.headers['Content-Type'] = 'application/json'
        resp = self._session.send(prepped)
    
    def save_state_transactional(self, actor_type, actor_id, states) -> None:
        """
        [
            {
                "operation": "upsert",
                "request": {
                    "key": "key1",
                    "value": "myData"
                }
            },
            {
                "operation": "delete",
                "request": {
                    "key": "key2"
                }
            }
        ]
        """
        url = '{}/state'.format(self._get_base_url(actor_type, actor_id))

        body_bytes = b'' if states is None else json.dumps(states)
        req = requests.Request(method='PUT', url=url, data=body_bytes)
        prepped = req.prepare()
        prepped.headers['Content-Type'] = 'application/json'
        resp = self._session.send(prepped)
    
    def get_state(self, actor_type, actor_id, key) -> object:
        url = '{}/state/{}'.format(
            self._get_base_url(actor_type, actor_id),
            key)

        req = requests.Request(method='GET', url=url)
        prepped = req.prepare()
        resp = self._session.send(prepped)

        return resp.json()
    
    def delete_state(self, actor_type, actor_id, key) -> None:
        url = '{}/state/{}'.format(
            self._get_base_url(actor_type, actor_id),
            key)

        req = requests.Request(method='DELETE', url=url)
        prepped = req.prepare()
        resp = self._session.send(prepped)
    
    def create_reminder(self, actor_type, actor_id, name, reminder_data) -> None:
        """
        {
            "data": "someData",
            "dueTime": "1m",
            "period": "20s"
        }
        """
        url = '{}/reminders/{}'.format(
            self._get_base_url(actor_type, actor_id),
            name)

        body_bytes = b'' if reminder_data is None else json.dumps(reminder_data)
        req = requests.Request(method='PUT', url=url, data=body_bytes)
        prepped = req.prepare()
        prepped.headers['Content-Type'] = 'application/json'
        resp = self._session.send(prepped)

    def get_reminder(self, actor_type, actor_id, name) -> DaprActorReminder:

        url = '{}/reminders/{}'.format(
            self._get_base_url(actor_type, actor_id),
            name)

        req = requests.Request(method='GET', url=url)
        prepped = req.prepare()
        prepped.headers['Content-Type'] = 'application/json'
        resp = self._session.send(prepped)

        return resp.json()
    
    def delete_reminder(self, actor_type, actor_id, name) -> None:

        url = '{}/reminders/{}'.format(
            self._get_base_url(actor_type, actor_id),
            name)

        req = requests.Request(method='DELETE', url=url)
        prepped = req.prepare()
        prepped.headers['Content-Type'] = 'application/json'
        resp = self._session.send(prepped)

    def create_timer(self, actor_type, actor_id, name, timer_data) -> None:
        """
        {
            "data": "someData",
            "dueTime": "1m",
            "period": "20s",
            "callback": "Actor.myEventHandler"
        }
        """
        url = '{}/timers/{}'.format(
            self._get_base_url(actor_type, actor_id),
            name)

        body_bytes = b'' if timer_data is None else json.dumps(timer_data)
        req = requests.Request(method='PUT', url=url, data=body_bytes)
        prepped = req.prepare()
        prepped.headers['Content-Type'] = 'application/json'
        resp = self._session.send(prepped)
    
    def delete_timer(self, actor_type, actor_id, name) -> None:
        url = '{}/timers/{}'.format(
            self._get_base_url(actor_type, actor_id),
            name)

        req = requests.Request(method='DELETE', url=url)
        prepped = req.prepare()
        prepped.headers['Content-Type'] = 'application/json'
        resp = self._session.send(prepped)
