# -*- coding: utf-8 -*-
# Copyright 2023 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from dataclasses import dataclass
from datetime import timedelta
import random
from time import sleep
import dapr.ext.workflow as wf

wfr = wf.WorkflowRuntime()


@dataclass
class JobStatus:
    job_id: str
    is_healthy: bool


@wfr.workflow(name='status_monitor')
def status_monitor_workflow(ctx: wf.DaprWorkflowContext, job: JobStatus):
    # poll a status endpoint associated with this job
    status = yield ctx.call_activity(check_status, input=job)
    if not ctx.is_replaying:
        print(f"Job '{job.job_id}' is {status}.")

    if status == 'healthy':
        job.is_healthy = True
        next_sleep_interval = 60  # check less frequently when healthy
    else:
        if job.is_healthy:
            job.is_healthy = False
            ctx.call_activity(send_alert, input=f"Job '{job.job_id}' is unhealthy!")
        next_sleep_interval = 5  # check more frequently when unhealthy

    yield ctx.create_timer(fire_at=timedelta(seconds=next_sleep_interval))

    # restart from the beginning with a new JobStatus input
    ctx.continue_as_new(job)


@wfr.activity
def check_status(ctx, _) -> str:
    return random.choice(['healthy', 'unhealthy'])


@wfr.activity
def send_alert(ctx, message: str):
    print(f'*** Alert: {message}')


if __name__ == '__main__':
    wfr.start()
    sleep(10)  # wait for workflow runtime to start

    wf_client = wf.DaprWorkflowClient()
    job_id = 'job1'
    status = None
    try:
        status = wf_client.get_workflow_state(job_id)
    except Exception:
        pass
    if not status or status.runtime_status.name != 'RUNNING':
        instance_id = wf_client.schedule_new_workflow(
            workflow=status_monitor_workflow,
            input=JobStatus(job_id=job_id, is_healthy=True),
            instance_id=job_id,
        )
        print(f'Workflow started. Instance ID: {instance_id}')
    else:
        print(f'Workflow already running. Instance ID: {job_id}')

    input('Press Enter to stop...\n')
    wfr.shutdown()
