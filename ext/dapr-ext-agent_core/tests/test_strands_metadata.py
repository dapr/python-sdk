#!/usr/bin/env python3
"""
Test script to verify Strands metadata integration with agent registry.
"""

import sys
import os

# Add the extensions to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ext/dapr-ext-agent_core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ext/dapr-ext-strands'))

from dapr.ext.agent_core.types import SupportedFrameworks
from dapr.ext.agent_core.introspection import detect_framework
from dapr.ext.agent_core.mapping.strands import StrandsMapper


def test_supported_frameworks():
    """Test that STRANDS framework is in the enum."""
    print("✓ Testing SupportedFrameworks enum...")
    assert hasattr(SupportedFrameworks, 'STRANDS'), "STRANDS not in SupportedFrameworks"
    assert SupportedFrameworks.STRANDS.value == 'strands', "STRANDS value incorrect"
    print("  ✓ STRANDS framework is supported")
    return True


def test_mapper_instantiation():
    """Test that StrandsMapper can be instantiated."""
    print("✓ Testing StrandsMapper instantiation...")
    mapper = StrandsMapper()
    assert mapper is not None, "Failed to instantiate StrandsMapper"
    print("  ✓ StrandsMapper instantiated successfully")
    return True


def test_mapper_metadata_extraction():
    """Test that StrandsMapper can extract metadata from a mock object."""
    print("✓ Testing StrandsMapper metadata extraction...")
    
    # Create a mock DaprSessionManager-like object
    class MockSessionManager:
        def __init__(self):
            self._state_store_name = "test-statestore"
            self._session_id = "test-session-123"
    
    mock_manager = MockSessionManager()
    mapper = StrandsMapper()
    
    metadata = mapper.map_agent_metadata(mock_manager, schema_version="1.0.0")
    
    assert metadata.schema_version == "1.0.0", "Schema version mismatch"
    assert metadata.agent.type == "Strands", "Agent type mismatch"
    assert metadata.agent.role == "Session Manager", "Agent role mismatch"
    assert metadata.memory.type == "DaprSessionManager", "Memory type mismatch"
    assert metadata.memory.session_id == "test-session-123", "Session ID mismatch"
    assert metadata.memory.statestore == "test-statestore", "State store mismatch"
    assert metadata.name == "strands-session-test-session-123", "Agent name mismatch"
    
    print("  ✓ Metadata extraction successful")
    print(f"    - Agent type: {metadata.agent.type}")
    print(f"    - Agent name: {metadata.name}")
    print(f"    - Memory type: {metadata.memory.type}")
    print(f"    - Session ID: {metadata.memory.session_id}")
    print(f"    - State store: {metadata.memory.statestore}")
    return True


def test_framework_detection():
    """Test that detect_framework can identify a Strands object."""
    print("✓ Testing framework detection...")
    
    class MockSessionManager:
        def __init__(self):
            self._state_store_name = "test-statestore"
            self._session_id = "test-session-123"
    
    MockSessionManager.__name__ = "DaprSessionManager"
    mock_manager = MockSessionManager()
    
    framework = detect_framework(mock_manager)
    assert framework == "strands", f"Expected 'strands', got '{framework}'"
    
    print("  ✓ Framework detection successful")
    print(f"    - Detected framework: {framework}")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Testing Strands Metadata Integration")
    print("="*60 + "\n")
    
    tests = [
        test_supported_frameworks,
        test_mapper_instantiation,
        test_mapper_metadata_extraction,
        test_framework_detection,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  ✗ Test failed: {e}")
            failed += 1
        print()
    
    print("="*60)
    print(f"Tests completed: {passed} passed, {failed} failed")
    print("="*60 + "\n")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
