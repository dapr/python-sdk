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
import os

from durabletask.task import TaskFailedError
import dapr.ext.workflow as wf
import time

wfr = wf.WorkflowRuntime()


@wfr.workflow
def app2_workflow(ctx: wf.DaprWorkflowContext):
    print(f'app2 - received workflow call', flush=True)
    if os.getenv('ERROR_WORKFLOW_MODE', 'false') == 'true':
        print(f'app2 - raising error in workflow due to error mode being enabled', flush=True)
        raise ValueError('Error in workflow due to error mode being enabled')
    print(f'app2 - triggering app3 activity', flush=True)
    try:
        retry_policy = wf.RetryPolicy(
            max_number_of_attempts=2,
            first_retry_interval=timedelta(milliseconds=100),
            max_retry_interval=timedelta(seconds=3),
        )
        result = yield ctx.call_activity(
            'app3_activity', input=None, app_id='wfexample3', retry_policy=retry_policy
        )
        print(f'app2 - received activity result', flush=True)
    except TaskFailedError as e:
        print(f'app2 - received activity error from app3', flush=True)

    print(f'app2 - returning workflow result', flush=True)
    return 2


if __name__ == '__main__':
    wfr.start()
    time.sleep(15)  # wait for workflow runtime to start
    wfr.shutdown()
