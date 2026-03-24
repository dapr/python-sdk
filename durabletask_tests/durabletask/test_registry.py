"""
Copyright 2025 The Dapr Authors
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

"""Unit tests for the _Registry class validation logic."""

import pytest

from durabletask import worker


def test_registry_add_orchestrator_none():
    """Test that adding a None orchestrator raises ValueError."""
    registry = worker._Registry()

    with pytest.raises(ValueError, match="An orchestrator function argument is required"):
        registry.add_orchestrator(None)


def test_registry_add_named_orchestrator_empty_name():
    """Test that adding an orchestrator with empty name raises ValueError."""
    registry = worker._Registry()

    def dummy_orchestrator(ctx, input):
        return "done"

    with pytest.raises(ValueError, match="A non-empty orchestrator name is required"):
        registry.add_named_orchestrator("", dummy_orchestrator)


def test_registry_add_orchestrator_duplicate():
    """Test that adding a duplicate orchestrator raises ValueError."""
    registry = worker._Registry()

    def dummy_orchestrator(ctx, input):
        return "done"

    name = "test_orchestrator"
    registry.add_named_orchestrator(name, dummy_orchestrator)

    with pytest.raises(ValueError, match=f"A '{name}' orchestrator already exists"):
        registry.add_named_orchestrator(name, dummy_orchestrator)


def test_registry_add_activity_none():
    """Test that adding a None activity raises ValueError."""
    registry = worker._Registry()

    with pytest.raises(ValueError, match="An activity function argument is required"):
        registry.add_activity(None)


def test_registry_add_named_activity_empty_name():
    """Test that adding an activity with empty name raises ValueError."""
    registry = worker._Registry()

    def dummy_activity(ctx, input):
        return "done"

    with pytest.raises(ValueError, match="A non-empty activity name is required"):
        registry.add_named_activity("", dummy_activity)


def test_registry_add_activity_duplicate():
    """Test that adding a duplicate activity raises ValueError."""
    registry = worker._Registry()

    def dummy_activity(ctx, input):
        return "done"

    name = "test_activity"
    registry.add_named_activity(name, dummy_activity)

    with pytest.raises(ValueError, match=f"A '{name}' activity already exists"):
        registry.add_named_activity(name, dummy_activity)


def test_registry_get_orchestrator_exists():
    """Test retrieving an existing orchestrator."""
    registry = worker._Registry()

    def dummy_orchestrator(ctx, input):
        return "done"

    name = registry.add_orchestrator(dummy_orchestrator)
    retrieved, _ = registry.get_orchestrator(name)

    assert retrieved is dummy_orchestrator


def test_registry_get_orchestrator_not_exists():
    """Test retrieving a non-existent orchestrator returns None."""
    registry = worker._Registry()

    retrieved, _ = registry.get_orchestrator("non_existent")

    assert retrieved is None


def test_registry_get_activity_exists():
    """Test retrieving an existing activity."""
    registry = worker._Registry()

    def dummy_activity(ctx, input):
        return "done"

    name = registry.add_activity(dummy_activity)
    retrieved = registry.get_activity(name)

    assert retrieved is dummy_activity


def test_registry_get_activity_not_exists():
    """Test retrieving a non-existent activity returns None."""
    registry = worker._Registry()

    retrieved = registry.get_activity("non_existent")

    assert retrieved is None


def test_registry_add_multiple_orchestrators():
    """Test adding multiple different orchestrators."""
    registry = worker._Registry()

    def orchestrator1(ctx, input):
        return "one"

    def orchestrator2(ctx, input):
        return "two"

    name1 = registry.add_orchestrator(orchestrator1)
    name2 = registry.add_orchestrator(orchestrator2)

    assert name1 != name2
    orchestrator1, _ = registry.get_orchestrator(name1)
    orchestrator2, _ = registry.get_orchestrator(name2)
    assert orchestrator1 is not None
    assert orchestrator2 is not None


def test_registry_add_multiple_activities():
    """Test adding multiple different activities."""
    registry = worker._Registry()

    def activity1(ctx, input):
        return "one"

    def activity2(ctx, input):
        return "two"

    name1 = registry.add_activity(activity1)
    name2 = registry.add_activity(activity2)

    assert name1 != name2
    assert registry.get_activity(name1) is activity1
    assert registry.get_activity(name2) is activity2


def test_registry_add_named_versioned_orchestrators():
    """Test adding versioned orchestrators."""
    registry = worker._Registry()

    def orchestrator1(ctx, input):
        return "one"

    def orchestrator2(ctx, input):
        return "two"

    def orchestrator3(ctx, input):
        return "two"

    registry.add_named_orchestrator(name="orchestrator", fn=orchestrator1, version_name="v1")
    registry.add_named_orchestrator(
        name="orchestrator", fn=orchestrator2, version_name="v2", is_latest=True
    )
    registry.add_named_orchestrator(name="orchestrator", fn=orchestrator3, version_name="v3")

    orquestrator, version = registry.get_orchestrator(name="orchestrator")
    assert orquestrator is orchestrator2
    assert version == "v2"

    orquestrator, version = registry.get_orchestrator(name="orchestrator", version_name="v1")
    assert orquestrator is orchestrator1
    assert version == "v1"

    orquestrator, version = registry.get_orchestrator(name="orchestrator", version_name="v2")
    assert orquestrator is orchestrator2
    assert version == "v2"

    orquestrator, version = registry.get_orchestrator(name="orchestrator", version_name="v3")
    assert orquestrator is orchestrator3
    assert version == "v3"

    with pytest.raises(worker.VersionNotRegisteredException):
        registry.get_orchestrator(name="orchestrator", version_name="v4")

    orquestrator, _ = registry.get_orchestrator(name="non-existent")
    assert orquestrator is None
