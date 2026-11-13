# -*- coding: utf-8 -*-
# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Workflow schedule example: start a workflow on a cron schedule.

1. ``create_workflow_schedule()`` starts ``report_workflow`` every 2 seconds,
   for 3 runs in all.
2. ``trigger_workflow_schedule()`` starts one of those runs now, without moving
   the next scheduled one.
3. ``get_workflow_schedule()`` is polled until the schedule has no runs left.
4. ``iter_workflow_instance_ids(instance_id_prefix=...)`` lists the runs, whose
   instance IDs all start with ``"<schedule name>_"``.
5. ``delete_workflow_schedule()`` removes the schedule. Its runs are left alone,
   so they are purged here.
"""

import time

import dapr.ext.workflow as wf

wfr = wf.WorkflowRuntime()

schedule_name = 'report-every-2s'


@wfr.workflow(name='report_workflow')
def report_workflow(ctx: wf.DaprWorkflowContext, region: str):
    return f'report for {region}'


def wait_until_inactive(
    client: wf.DaprWorkflowClient, name: str, timeout_seconds: float = 60
) -> wf.WorkflowSchedule:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        schedule = client.get_workflow_schedule(name)
        if schedule.status.state != wf.WorkflowScheduleState.ACTIVE:
            return schedule
        time.sleep(1)
    raise TimeoutError(f'schedule {name} still active after {timeout_seconds}s')


def list_schedule_names(client: wf.DaprWorkflowClient) -> list[str]:
    """Lists every schedule's name, following continuation tokens to the end.

    A page can hold fewer schedules than the page size while more remain.
    """
    names: list[str] = []
    token: str | None = None
    while True:
        page = client.list_workflow_schedules(continuation_token=token)
        names += [schedule.name for schedule in page.schedules]
        token = page.continuation_token
        if token is None:
            return names


def main():
    client = wf.DaprWorkflowClient()
    wfr.start()
    # The runtime's worker threads would keep the process alive if a call failed.
    try:
        client.create_workflow_schedule(
            schedule_name, report_workflow, '@every 2s', input='eu', repeats=3, overwrite=True
        )
        print(f'*** created schedule {schedule_name}', flush=True)

        run_id = client.trigger_workflow_schedule(schedule_name)
        run_state = client.wait_for_workflow_completion(run_id, timeout_in_seconds=30)
        print(
            f'*** triggered run finished: status={run_state.runtime_status.name}'
            f' result={run_state.serialized_output}',
            flush=True,
        )

        schedule = wait_until_inactive(client, schedule_name)
        print(
            f'*** schedule finished: state={schedule.status.state.name}'
            f' runs={schedule.status.run_count}',
            flush=True,
        )

        present = schedule_name in list_schedule_names(client)
        print(f'*** list: schedule present={present}', flush=True)

        run_ids = list(client.iter_workflow_instance_ids(instance_id_prefix=f'{schedule_name}_'))
        print(f'*** runs: {len(run_ids)}', flush=True)

        client.delete_workflow_schedule(schedule_name)
        for instance_id in run_ids:
            client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)
            client.purge_workflow(instance_id)
        print('*** deleted the schedule and purged its runs', flush=True)
    finally:
        wfr.shutdown()
        client.close()


if __name__ == '__main__':
    main()
