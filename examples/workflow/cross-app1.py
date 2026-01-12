# -*- coding: utf-8 -*-
# Copyright 2025 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from datetime import timedelta

from durabletask.task import TaskFailedError
import dapr.ext.workflow as wf
import time

wfr = wf.WorkflowRuntime()


@wfr.workflow
def app1_workflow(ctx: wf.DaprWorkflowContext):
    print(f'app1 - received workflow call', flush=True)
    print(f'app1 - triggering app2 workflow', flush=True)

    try:
        retry_policy = wf.RetryPolicy(
            max_number_of_attempts=2,
            first_retry_interval=timedelta(milliseconds=100),
            max_retry_interval=timedelta(seconds=3),
        )
        yield ctx.call_child_workflow(
            workflow='app2_workflow',
            input=None,
            app_id='wfexample2',
            retry_policy=retry_policy,
        )
        print(f'app1 - received workflow result', flush=True)
    except TaskFailedError as e:
        print(f'app1 - received workflow error from app2', flush=True)

    print(f'app1 - returning workflow result', flush=True)
    return 1


if __name__ == '__main__':
    wfr.start()
    time.sleep(10)  # wait for workflow runtime to start

    wf_client = wf.DaprWorkflowClient()
    print(f'app1 - triggering app1 workflow', flush=True)
    instance_id = wf_client.schedule_new_workflow(workflow=app1_workflow)

    # Wait for the workflow to complete
    time.sleep(7)

    wfr.shutdown()
