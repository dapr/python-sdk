# -*- coding: utf-8 -*-

from __future__ import annotations

import time

from dapr.ext.workflow import DaprWorkflowClient, WorkflowRuntime


def main():
    port = '50001'

    rt = WorkflowRuntime(port=port)

    def activity_noop(ctx):
        ei = ctx.execution_info
        # Return attempt (may be None if engine doesn't set it)
        return {
            'attempt': ei.attempt if ei else None,
            'workflow_id': ei.workflow_id if ei else None,
        }

    @rt.workflow(name='child-to-parent')
    def child(ctx, x):
        ei = ctx.execution_info
        out = yield ctx.call_activity(activity_noop, input=None)
        return {
            'child_workflow_name': ei.workflow_name if ei else None,
            'parent_instance_id': ei.parent_instance_id if ei else None,
            'activity': out,
        }

    @rt.workflow(name='parent')
    def parent(ctx, x):
        res = yield ctx.call_child_workflow(child, input={'x': x})
        return res

    rt.register_activity(activity_noop, name='activity_noop')

    rt.start()
    try:
        # Wait for the worker to be ready to accept work
        rt.wait_for_ready(timeout=10)

        client = DaprWorkflowClient(port=port)
        instance_id = client.schedule_new_workflow(parent, input=1)
        state = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=30)
        print('instance:', instance_id)
        print('runtime_status:', state.runtime_status if state else None)
        print('state:', state)
    finally:
        # Give a moment for logs to flush then shutdown
        time.sleep(0.5)
        rt.shutdown()


if __name__ == '__main__':
    main()
