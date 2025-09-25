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

import dapr.ext.workflow as wf
import time

wfr = wf.WorkflowRuntime()


@wfr.workflow
def app1_workflow(ctx: wf.DaprWorkflowContext):
    print(f'app1 - received workflow call', flush=True)
    print(f'app1 - triggering app2 workflow', flush=True)

    yield ctx.call_child_workflow(
        workflow='app2_workflow',
        input=None,
        app_id='wfexample2',
    )
    print(f'app1 - received workflow result', flush=True)
    print(f'app1 - returning workflow result', flush=True)

    return 1


if __name__ == '__main__':
    wfr.start()
    time.sleep(10)  # wait for workflow runtime to start

    wf_client = wf.DaprWorkflowClient()
    print(f'app1 - triggering app1 workflow', flush=True)
    instance_id = wf_client.schedule_new_workflow(workflow=app1_workflow)

    # Wait for the workflow to complete
    time.sleep(5)

    wfr.shutdown()
