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

"""Hosts the workflow that the client app drives cross-app.

Only this app registers the workflow. The caller in cross-app-client.py never
registers it and only holds a client.
"""

import threading

import dapr.ext.workflow as wf

wfr = wf.WorkflowRuntime()

stop = threading.Event()


@wfr.workflow
def hosted_workflow(ctx: wf.DaprWorkflowContext):
    print('host - workflow started', flush=True)
    payload = yield ctx.wait_for_external_event('Finish')
    print(f'host - received event with payload: {payload}', flush=True)
    return payload


if __name__ == '__main__':
    wfr.start()
    print('host - ready', flush=True)
    try:
        stop.wait(timeout=30)
    finally:
        wfr.shutdown()
