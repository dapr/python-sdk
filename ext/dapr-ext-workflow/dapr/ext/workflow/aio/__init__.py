# -*- coding: utf-8 -*-

from .dapr_workflow_client import DaprWorkflowClientAsync

# Public alias to mirror sync naming under aio namespace
DaprWorkflowClient = DaprWorkflowClientAsync

__all__ = [
    'DaprWorkflowClientAsync',
    'DaprWorkflowClient',
]
