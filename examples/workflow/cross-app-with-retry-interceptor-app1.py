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
Example: Default Retry Policy Interceptor for Cross-App Activities

This example demonstrates how to use workflow outbound interceptors to:
- Set default retry policies for all activities that don't have one
- Apply different retry policies based on the target app_id
- Preserve user-provided retry policies while adding defaults
"""

import time
from dataclasses import replace
from datetime import timedelta
from typing import Any, Callable

import dapr.ext.workflow as wf
from dapr.ext.workflow import (
    BaseWorkflowOutboundInterceptor,
    CallActivityRequest,
    CallChildWorkflowRequest,
)


def print_no_replay(ctx: wf.DaprWorkflowContext):
    """Returns a print function that only prints if not replaying"""
    if not ctx.is_replaying:
        return print
    else:
        return lambda *args, **kwargs: None


class DefaultRetryInterceptor(BaseWorkflowOutboundInterceptor):
    """Interceptor that sets default retry policies for activities and child workflows.

    This demonstrates how interceptors can inspect and modify retry_policy and app_id
    fields to provide consistent resilience behavior across your workflows.
    """

    def call_activity(
        self, request: CallActivityRequest, nxt: Callable[[CallActivityRequest], Any]
    ) -> Any:
        print = print_no_replay(
            request.workflow_ctx
        )  # print function that only prints if not replaying
        # Set default retry policy if none provided
        print(f'[Interceptor] call_activity called with request: {request}')
        retry_policy = request.retry_policy
        if retry_policy is None:
            # Apply different retry policies based on target app
            if request.app_id == 'wfexample-retry-app2':
                # More aggressive retry for cross-app calls
                retry_policy = wf.RetryPolicy(
                    max_number_of_attempts=4,  # 1 + 3 retries
                    first_retry_interval=timedelta(milliseconds=500),
                    max_retry_interval=timedelta(seconds=5),
                    backoff_coefficient=2.0,
                )
                print(
                    f'[Interceptor] Setting cross-app retry policy for activity {request.activity_name} -> {request.app_id}',
                )
            else:
                # Default retry for local activities
                retry_policy = wf.RetryPolicy(
                    max_number_of_attempts=2,
                    first_retry_interval=timedelta(milliseconds=100),
                    max_retry_interval=timedelta(seconds=2),
                )
                print(
                    f'[Interceptor] Setting default retry policy for activity {request.activity_name}',
                )
        else:
            print(
                f'[Interceptor] Preserving user-provided retry policy for {request.activity_name}',
            )

        # Forward with modified request using dataclasses.replace()
        return nxt(replace(request, retry_policy=retry_policy))

    def call_child_workflow(
        self, request: CallChildWorkflowRequest, nxt: Callable[[CallChildWorkflowRequest], Any]
    ) -> Any:
        # Could also set default retry for child workflows
        retry_policy = request.retry_policy
        if retry_policy is None and request.app_id is not None:
            retry_policy = wf.RetryPolicy(
                max_number_of_attempts=2,
                first_retry_interval=timedelta(milliseconds=200),
                max_retry_interval=timedelta(seconds=3),
            )
            print(
                f'[Interceptor] Setting retry policy for child workflow {request.workflow_name} -> {request.app_id}',
                flush=True,
            )

        return nxt(replace(request, retry_policy=retry_policy))


# Create runtime with the interceptor
wfr = wf.WorkflowRuntime(workflow_outbound_interceptors=[DefaultRetryInterceptor()])


@wfr.workflow
def app1_workflow(ctx: wf.DaprWorkflowContext):
    print = print_no_replay(ctx)  # print function that only prints if not replaying
    print('app1 - workflow started')

    # Call local activity (will get default retry policy from interceptor)
    print('app1 - calling local_activity')
    result1 = yield ctx.call_activity(local_activity, input='local-call')
    print(f'app1 - local_activity result: {result1}')

    # Call cross-app activity (will get cross-app retry policy from interceptor)
    print('app1 - calling cross-app activity')
    result2 = yield ctx.call_activity(
        'remote_activity', input='cross-app-call', app_id='wfexample-retry-app2'
    )
    print(f'app1 - remote_activity result: {result2}')

    # Call activity with explicit retry policy (interceptor preserves it)
    print('app1 - calling activity with explicit retry policy', flush=True)
    explicit_retry = wf.RetryPolicy(
        max_number_of_attempts=5,
        first_retry_interval=timedelta(milliseconds=50),
        max_retry_interval=timedelta(seconds=1),
    )
    result3 = yield ctx.call_activity(
        local_activity, input='explicit-retry', retry_policy=explicit_retry
    )
    print(f'app1 - explicit retry activity result: {result3}', flush=True)

    print('app1 - workflow completed', flush=True)
    return {'local': result1, 'remote': result2, 'explicit': result3}


@wfr.activity
def local_activity(ctx: wf.WorkflowActivityContext, input: str) -> str:
    print(f'app1 - local_activity called with input: {input}', flush=True)
    return f'local-result-{input}'


if __name__ == '__main__':
    wfr.start()
    time.sleep(10)  # wait for workflow runtime to start

    wf_client = wf.DaprWorkflowClient()
    print('app1 - scheduling workflow', flush=True)
    instance_id = wf_client.schedule_new_workflow(workflow=app1_workflow)
    print(f'app1 - workflow scheduled with instance_id: {instance_id}', flush=True)

    # Wait for the workflow to complete
    time.sleep(30)

    # Check workflow state
    state = wf_client.get_workflow_state(instance_id)
    if state:
        print(f'app1 - workflow status: {state.runtime_status.name}', flush=True)
        if state.serialized_output:
            print(f'app1 - workflow output: {state.serialized_output}', flush=True)

    wfr.shutdown()
