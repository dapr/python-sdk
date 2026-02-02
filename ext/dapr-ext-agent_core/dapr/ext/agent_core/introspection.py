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
"""

import gc
import inspect
from typing import Any, Optional


def find_agent_in_stack() -> Optional[Any]:
    """
    Walk up the call stack to find an agent/graph object.
    
    Currently supports:
    - LangGraph: CompiledStateGraph or SyncPregelLoop
    - Strands: DaprSessionManager
    
    Returns:
        The agent/graph object if found, None otherwise.
    """
    # First, try to find in the stack
    for frame_info in inspect.stack():
        frame_locals = frame_info.frame.f_locals
        
        # Look for 'self' in frame locals
        if 'self' in frame_locals:
            obj = frame_locals['self']
            obj_type = type(obj).__name__
            
            # LangGraph support - CompiledStateGraph
            if obj_type == 'CompiledStateGraph':
                return obj
            
            # Strands support - DaprSessionManager
            if obj_type == 'DaprSessionManager':
                return obj
            
            # If we found a checkpointer, use gc to find the graph that references it
            if obj_type == 'DaprCheckpointer':
                # Use garbage collector to find objects referencing this checkpointer
                referrers = gc.get_referrers(obj)
                for ref in referrers:
                    ref_type = type(ref).__name__
                    if ref_type == 'CompiledStateGraph':
                        return ref
    
    return None


def detect_framework(agent: Any) -> Optional[str]:
    """
    Detect the framework type from an agent object.
    
    Args:
        agent: The agent object to inspect.
    
    Returns:
        Framework name string if detected, None otherwise.
    """
    agent_type = type(agent).__name__
    agent_module = type(agent).__module__
    
    # LangGraph
    if agent_type == 'CompiledStateGraph' or 'langgraph' in agent_module:
        return 'langgraph'
    
    # Dapr Agents
    if 'dapr_agents' in agent_module:
        return 'dapr_agents'
    
    # Strands
    if agent_type == 'DaprSessionManager' or 'strands' in agent_module:
        return 'strands'
    
    return None
