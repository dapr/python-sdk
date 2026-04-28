import uuid
from datetime import datetime, timedelta, timezone

import pytest

from dapr.clients import Job
from dapr.clients.exceptions import DaprGrpcError

# The jobs API re-emits the alpha warnings on every test run.
pytestmark = pytest.mark.filterwarnings('ignore::UserWarning')


def _future(days: int) -> str:
    """Return an RFC3339 timestamp ``days`` days from now in UTC."""
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')


@pytest.fixture(scope='module')
def client(dapr_env):
    return dapr_env.start_sidecar(app_id='test-jobs')


def _unique_name(prefix: str) -> str:
    return f'{prefix}-{uuid.uuid4().hex[:8]}'


def test_schedule_then_get_returns_job(client):
    name = _unique_name('job-get')
    due = _future(days=365)

    client.schedule_job_alpha1(Job(name=name, due_time=due))
    try:
        retrieved = client.get_job_alpha1(name=name)
        assert retrieved.name == name
        assert retrieved.due_time == due
    finally:
        client.delete_job_alpha1(name=name)


def test_schedule_with_schedule_expression(client):
    name = _unique_name('job-sched')
    job_recurring = Job(name=name, schedule='@every 1h', due_time=_future(days=365), repeats=1)

    client.schedule_job_alpha1(job_recurring)
    try:
        retrieved = client.get_job_alpha1(name=name)
        assert retrieved.schedule == '@every 1h'
        assert retrieved.repeats == 1
    finally:
        client.delete_job_alpha1(name=name)


def test_schedule_without_overwrite_rejects_duplicate(client):
    name = _unique_name('job-dup')
    due = _future(days=365)

    client.schedule_job_alpha1(Job(name=name, due_time=due))
    try:
        with pytest.raises(DaprGrpcError):
            client.schedule_job_alpha1(Job(name=name, due_time=due))
    finally:
        client.delete_job_alpha1(name=name)


def test_schedule_with_overwrite_replaces_existing(client):
    name = _unique_name('job-overwrite')
    updated_due = _future(days=730)
    job_original = Job(name=name, due_time=_future(days=365))
    job_replacement = Job(name=name, due_time=updated_due)

    client.schedule_job_alpha1(job_original)
    try:
        client.schedule_job_alpha1(job_replacement, overwrite=True)
        retrieved = client.get_job_alpha1(name=name)
        assert retrieved.due_time == updated_due
    finally:
        client.delete_job_alpha1(name=name)


def test_delete_then_get_raises_not_found(client):
    name = _unique_name('job-del')
    job = Job(name=name, due_time=_future(days=365))

    client.schedule_job_alpha1(job)
    client.delete_job_alpha1(name=name)
    with pytest.raises(DaprGrpcError):
        client.get_job_alpha1(name=name)


def test_schedule_with_empty_name_raises(client):
    job_unnamed = Job(name='', due_time=_future(days=365))

    with pytest.raises(ValueError):
        client.schedule_job_alpha1(job_unnamed)


def test_schedule_without_schedule_or_due_time_raises(client):
    job_timeless = Job(name=_unique_name('job-nosched'))

    with pytest.raises(ValueError):
        client.schedule_job_alpha1(job_timeless)
