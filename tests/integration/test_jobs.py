from datetime import datetime, timedelta, timezone

import pytest
from naming_utils import unique_name

from dapr.clients import Job
from dapr.clients.exceptions import DaprGrpcError

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

    client.schedule_job_alpha1(Job(name=name, due_time=due))
    try:
        retrieved = client.get_job_alpha1(name=name)
        assert retrieved.name == name
        assert retrieved.due_time == due
    finally:
        client.delete_job_alpha1(name=name)


def test_delete_removes_job(client):
    name = unique_name(prefix='sync-job-del-')
    due = _future(days=365)

    client.schedule_job_alpha1(Job(name=name, due_time=due))
    client.delete_job_alpha1(name=name)

    with pytest.raises(DaprGrpcError):
        client.get_job_alpha1(name=name)


def test_schedule_with_recurring_schedule(client):
    name = unique_name(prefix='sync-job-recurring-')
    schedule = '@every 1h'

    client.schedule_job_alpha1(Job(name=name, schedule=schedule, repeats=10))
    try:
        retrieved = client.get_job_alpha1(name=name)
        assert retrieved.schedule == schedule
        assert retrieved.repeats == 10
    finally:
        client.delete_job_alpha1(name=name)


def test_schedule_without_schedule_or_due_time_raises(client):
    with pytest.raises(ValueError):
        client.schedule_job_alpha1(Job(name=unique_name(prefix='sync-job-bad-')))


def test_schedule_with_blank_name_raises(client):
    with pytest.raises(ValueError):
        client.schedule_job_alpha1(Job(name='', due_time=_future(days=1)))


def test_overwrite_replaces_existing_job(client):
    name = unique_name(prefix='sync-job-overwrite-')
    initial_due = _future(days=30)
    updated_due = _future(days=60)

    client.schedule_job_alpha1(Job(name=name, due_time=initial_due))
    try:
        client.schedule_job_alpha1(Job(name=name, due_time=updated_due), overwrite=True)
        retrieved = client.get_job_alpha1(name=name)
        assert retrieved.due_time == updated_due
    finally:
        client.delete_job_alpha1(name=name)
