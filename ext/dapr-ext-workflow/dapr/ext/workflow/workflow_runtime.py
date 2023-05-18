# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from typing import TypeVar
from durabletask import worker, task
from dapr.ext.workflow.workflow_context import Workflow
from dapr.ext.workflow.dapr_workflow_context import DaprWorkflowContext
from dapr.ext.workflow.workflow_activity_context import Activity, WorkflowActivityContext

T = TypeVar('T')
TInput = TypeVar('TInput')
TOutput = TypeVar('TOutput')


class WorkflowRuntime:
    """WorkflowRuntime is the entry point for registering workflows and activities.
    """

    def __init__(self):
        self.__worker = worker.TaskHubGrpcWorker()

    def register_workflow(self, fn: Workflow[TInput, TInput]):
        def orchestrationWrapper(ctx: task.OrchestrationContext, inp: TInput):
            """Responsible to call Workflow function in orchestrationWrapper"""
            daprWfContext = DaprWorkflowContext(ctx)
            return fn(daprWfContext, inp)

        self.__worker._registry.add_named_orchestrator(fn.__name__, orchestrationWrapper)

    def register_activity(self, fn: Activity):
        """Registers a workflow activity as a function that takes
           a specified input type and returns a specified output type.
        """
        def activityWrapper(ctx: task.ActivityContext, inp: TInput):
            """Responsible to call Activity function in activityWrapper"""
            wfActivityContext = WorkflowActivityContext(ctx)
            return fn(wfActivityContext, inp)

        self.__worker._registry.add_named_activity(fn.__name__, activityWrapper)

    def start(self):
        """Starts the listening for work items on a background thread."""
        self.__worker.start()

    def shutdown(self):
        """Stops the listening for work items on a background thread."""
        self.__worker.stop()
