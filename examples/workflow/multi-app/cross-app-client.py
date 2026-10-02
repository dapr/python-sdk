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

"""Drives a workflow owned by another app using client-level app_id.

Unlike multi-app1.py, which calls across apps from inside a workflow, this app
runs no workflow of its own. It passes app_id to the client operations, so each
one is applied to the instance hosted by cross-app-client-host.py. Whether the
caller is permitted is governed by the target app's WorkflowAccessPolicy.
"""

import dapr.ext.workflow as wf

HOST_APP_ID = 'wfcrossapphost'

if __name__ == '__main__':
    wf_client = wf.DaprWorkflowClient()

    print('client - scheduling a workflow on the host app', flush=True)
    instance_id = wf_client.schedule_new_workflow(
        workflow='hosted_workflow',
        app_id=HOST_APP_ID,
    )

    wf_client.wait_for_workflow_start(instance_id, app_id=HOST_APP_ID)
    state = wf_client.get_workflow_state(instance_id, app_id=HOST_APP_ID)
    print(f'client - remote workflow is {state.runtime_status.name}', flush=True)

    wf_client.pause_workflow(instance_id, app_id=HOST_APP_ID)
    print('client - paused the remote workflow', flush=True)
    wf_client.resume_workflow(instance_id, app_id=HOST_APP_ID)
    print('client - resumed the remote workflow', flush=True)

    wf_client.raise_workflow_event(instance_id, 'Finish', data='done', app_id=HOST_APP_ID)
    state = wf_client.wait_for_workflow_completion(instance_id, app_id=HOST_APP_ID)
    print(f'client - remote workflow is {state.runtime_status.name}', flush=True)

    wf_client.purge_workflow(instance_id, app_id=HOST_APP_ID)
    print('client - purged the remote workflow', flush=True)
