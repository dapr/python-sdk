# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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

from datetime import datetime, timedelta, timezone

import pytest

from dapr.clients import Job
from dapr.clients.exceptions import DaprGrpcError
from tests.naming_utils import unique_name

# The jobs API re-emits the alpha warnings on every test run.
pytestmark = pytest.mark.filterwarnings('ignore::UserWarning')


def _future(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')


@pytest.fixture(scope='module')
def client(dapr_env):
    return dapr_env.start_sidecar(app_id='test-jobs')


def test_schedule_then_get_returns_job(client):
    name = unique_name(prefix='sync-job-')
    due = _future(days=365)

    client.schedule_job(Job(name=name, due_time=due))
    try:
        retrieved = client.get_job(name=name)
        assert retrieved.name == name
        assert retrieved.due_time == due
    except Exception as exc:
        raise AssertionError(f'get_job did not return scheduled job {name}') from exc
    finally:
        client.delete_job(name=name)


def test_delete_removes_job(client):
    name = unique_name(prefix='sync-job-del-')
    due = _future(days=365)

    client.schedule_job(Job(name=name, due_time=due))
    client.delete_job(name=name)

    with pytest.raises(DaprGrpcError):
        client.get_job(name=name)


def test_schedule_with_recurring_schedule(client):
    name = unique_name(prefix='sync-job-recurring-')
    schedule = '@every 1h'

    client.schedule_job(Job(name=name, schedule=schedule, repeats=10))
    try:
        retrieved = client.get_job(name=name)
        assert retrieved.schedule == schedule
        assert retrieved.repeats == 10
    except Exception as exc:
        raise AssertionError(f'Recurring schedule failed for job {name}') from exc
    finally:
        client.delete_job(name=name)


def test_schedule_without_schedule_or_due_time_raises(client):
    with pytest.raises(ValueError):
        client.schedule_job(Job(name=unique_name(prefix='sync-job-bad-')))


def test_schedule_with_blank_name_raises(client):
    with pytest.raises(ValueError):
        client.schedule_job(Job(name='', due_time=_future(days=1)))


def test_overwrite_replaces_existing_job(client):
    name = unique_name(prefix='sync-job-overwrite-')
    initial_due = _future(days=30)
    updated_due = _future(days=60)

    client.schedule_job(Job(name=name, due_time=initial_due))
    try:
        client.schedule_job(Job(name=name, due_time=updated_due), overwrite=True)
        retrieved = client.get_job(name=name)
        assert retrieved.due_time == updated_due
    except Exception as exc:
        raise AssertionError(f'overwrite=True did not replace due_time for job {name}') from exc
    finally:
        client.delete_job(name=name)
