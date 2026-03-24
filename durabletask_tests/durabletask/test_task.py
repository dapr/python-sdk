# Copyright (c) The Dapr Authors.
# Licensed under the MIT License.

"""Unit tests for durabletask.task primitives."""

from durabletask import task


def test_when_all_empty_returns_successfully():
    """task.when_all([]) should complete immediately and return an empty list."""
    when_all_task = task.when_all([])

    assert when_all_task.is_complete
    assert when_all_task.get_result() == []


def test_when_any_empty_returns_successfully():
    """task.when_any([]) should complete immediately and return an empty list."""
    when_any_task = task.when_any([])

    assert when_any_task.is_complete
    assert when_any_task.get_result() == []


def test_when_all_happy_path_returns_ordered_results_and_completes_last():
    c1 = task.CompletableTask()
    c2 = task.CompletableTask()
    c3 = task.CompletableTask()

    all_task = task.when_all([c1, c2, c3])

    assert not all_task.is_complete

    c2.complete("two")

    assert not all_task.is_complete

    c1.complete("one")

    assert not all_task.is_complete

    c3.complete("three")

    assert all_task.is_complete

    assert all_task.get_result() == ["one", "two", "three"]


def test_when_all_is_composable_with_when_any():
    c1 = task.CompletableTask()
    c2 = task.CompletableTask()

    any_task = task.when_any([c1, c2])
    all_task = task.when_all([any_task])

    assert not any_task.is_complete
    assert not all_task.is_complete

    c2.complete("two")

    assert any_task.is_complete
    assert all_task.is_complete
    assert all_task.get_result() == [c2]


def test_when_any_is_composable_with_when_all():
    c1 = task.CompletableTask()
    c2 = task.CompletableTask()
    c3 = task.CompletableTask()

    all_task1 = task.when_all([c1, c2])
    all_task2 = task.when_all([c3])
    any_task = task.when_any([all_task1, all_task2])

    assert not any_task.is_complete
    assert not all_task1.is_complete
    assert not all_task2.is_complete

    c1.complete("one")

    assert not any_task.is_complete
    assert not all_task1.is_complete
    assert not all_task2.is_complete

    c2.complete("two")

    assert any_task.is_complete
    assert all_task1.is_complete
    assert not all_task2.is_complete

    assert any_task.get_result() == all_task1


def test_when_any_happy_path_returns_winner_task_and_completes_on_first():
    a = task.CompletableTask()
    b = task.CompletableTask()

    any_task = task.when_any([a, b])

    assert not any_task.is_complete

    b.complete("B")

    assert any_task.is_complete

    winner = any_task.get_result()

    assert winner is b

    assert winner.get_result() == "B"

    # Completing the other child should not change the winner
    a.complete("A")

    assert any_task.get_result() is b
