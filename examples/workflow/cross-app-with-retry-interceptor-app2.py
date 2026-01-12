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

"""
App2: Remote Activity Provider

This app provides the remote_activity that app1 calls cross-app.
It demonstrates how retry policies set by interceptors work across app boundaries.
"""

import os
import time

import dapr.ext.workflow as wf


def print_no_replay(ctx: wf.DaprWorkflowContext):
    """Returns a print function that only prints if not replaying"""
    if not ctx.is_replaying:
        return print
    else:
        return lambda *args, **kwargs: None


RETRY_ATTEMPT = 0

wfr = wf.WorkflowRuntime()


@wfr.activity
def remote_activity(ctx: wf.WorkflowActivityContext, input: str) -> str:
    print(f'app2 - remote_activity called with input: {input}', flush=True)

    # Optionally simulate failures to see retry behavior
    if os.getenv('SIMULATE_FAILURE', 'false') == 'true':
        global RETRY_ATTEMPT  # NOTE: this is a hack to simulate a failure and see the retry behavior. DO NOT DO THIS IN PRODUCTION as it is not deterministic.
        RETRY_ATTEMPT += 1
        if RETRY_ATTEMPT < 3:
            print(f'app2 - simulating temporary failure, attempt {RETRY_ATTEMPT}', flush=True)
            raise ValueError('Simulated activity failure')
        else:
            # failure resolved
            print(f'app2 - simulated failure resolved, attempt {RETRY_ATTEMPT}', flush=True)

    print('app2 - remote_activity completed successfully', flush=True)
    return f'remote-result-{input}'


if __name__ == '__main__':
    print('app2 - starting workflow runtime', flush=True)
    wfr.start()
    print('app2 - workflow runtime started, waiting...', flush=True)
    time.sleep(30)  # keep running longer to serve cross-app calls
    print('app2 - shutting down', flush=True)
    wfr.shutdown()
