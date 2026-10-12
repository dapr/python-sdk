# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Workflow host for cross-app integration tests.

Registers a workflow that blocks on an external event so that every
client-level operation (get, pause, resume, raise event, terminate, purge) is
observable against a running instance. The runtime dials out to its sidecar
over gRPC, so unlike the actor and pubsub hosts this app serves no app channel
and daprd is started without an --app-port.
"""

import signal
import threading
from typing import Any

from dapr.ext.workflow import DaprWorkflowContext, WorkflowRuntime

WORKFLOW_NAME = 'CrossAppWaitForEvent'
EVENT_NAME = 'Finish'


def wait_for_event_workflow(ctx: DaprWorkflowContext, wf_input: Any) -> Any:
    """Blocks until EVENT_NAME arrives, then returns its payload."""
    payload = yield ctx.wait_for_external_event(EVENT_NAME)
    return payload


def main() -> None:
    runtime = WorkflowRuntime()
    runtime.register_workflow(wait_for_event_workflow, name=WORKFLOW_NAME)
    runtime.start()

    # The test drives everything through the sidecar, so this process just has
    # to stay alive until it is torn down with the sidecar's process group.
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    try:
        stop.wait()
    finally:
        runtime.shutdown()


if __name__ == '__main__':
    main()
