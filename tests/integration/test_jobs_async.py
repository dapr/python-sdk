from datetime import datetime, timedelta, timezone

import pytest

from dapr.aio.clients import DaprClient as AsyncDaprClient
from dapr.clients import Job
from dapr.clients.exceptions import DaprGrpcError
from tests.naming_utils import unique_name

GRPC_ADDRESS = '127.0.0.1:50001'

# The jobs API re-emits the alpha warnings on every test run.
pytestmark = pytest.mark.filterwarnings('ignore::UserWarning')


def _future(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')


@pytest.fixture(scope='module')
def sidecar(dapr_env):
    dapr_env.start_sidecar(app_id='test-jobs-async')


async def test_schedule_then_get_returns_job(sidecar):
    name = unique_name(prefix='async-job-')
    due = _future(days=365)

    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        await d.schedule_job_alpha1(Job(name=name, due_time=due))
        try:
            retrieved = await d.get_job_alpha1(name=name)
            assert retrieved.name == name
            assert retrieved.due_time == due
        except Exception as exc:
            raise AssertionError(f'get_job_alpha1 did not return scheduled job {name}') from exc
        finally:
            await d.delete_job_alpha1(name=name)


async def test_delete_removes_job(sidecar):
    name = unique_name(prefix='async-job-del-')
    due = _future(days=365)

    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        await d.schedule_job_alpha1(Job(name=name, due_time=due))
        await d.delete_job_alpha1(name=name)

        with pytest.raises(DaprGrpcError):
            await d.get_job_alpha1(name=name)
