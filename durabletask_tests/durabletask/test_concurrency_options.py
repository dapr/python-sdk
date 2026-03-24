# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os

from durabletask.worker import ConcurrencyOptions, TaskHubGrpcWorker


def test_default_concurrency_options():
    """Test that default concurrency options work correctly."""
    options = ConcurrencyOptions()
    processor_count = os.cpu_count() or 1
    expected_default = 100 * processor_count
    expected_workers = processor_count + 4

    assert options.maximum_concurrent_activity_work_items == expected_default
    assert options.maximum_concurrent_orchestration_work_items == expected_default
    assert options.maximum_thread_pool_workers == expected_workers


def test_custom_concurrency_options():
    """Test that custom concurrency options work correctly."""
    options = ConcurrencyOptions(
        maximum_concurrent_activity_work_items=50,
        maximum_concurrent_orchestration_work_items=25,
        maximum_thread_pool_workers=30,
    )

    assert options.maximum_concurrent_activity_work_items == 50
    assert options.maximum_concurrent_orchestration_work_items == 25
    assert options.maximum_thread_pool_workers == 30


def test_partial_custom_options():
    """Test that partially specified options use defaults for unspecified values."""
    processor_count = os.cpu_count() or 1
    expected_default = 100 * processor_count
    expected_workers = processor_count + 4

    options = ConcurrencyOptions(maximum_concurrent_activity_work_items=30)

    assert options.maximum_concurrent_activity_work_items == 30
    assert options.maximum_concurrent_orchestration_work_items == expected_default
    assert options.maximum_thread_pool_workers == expected_workers


def test_worker_with_concurrency_options():
    """Test that TaskHubGrpcWorker accepts concurrency options."""
    options = ConcurrencyOptions(
        maximum_concurrent_activity_work_items=10,
        maximum_concurrent_orchestration_work_items=20,
        maximum_thread_pool_workers=15,
    )

    worker = TaskHubGrpcWorker(concurrency_options=options)

    assert worker.concurrency_options == options


def test_worker_default_options():
    """Test that TaskHubGrpcWorker uses default options when no parameters are provided."""
    worker = TaskHubGrpcWorker()

    processor_count = os.cpu_count() or 1
    expected_default = 100 * processor_count
    expected_workers = processor_count + 4

    assert worker.concurrency_options.maximum_concurrent_activity_work_items == expected_default
    assert (
        worker.concurrency_options.maximum_concurrent_orchestration_work_items == expected_default
    )
    assert worker.concurrency_options.maximum_thread_pool_workers == expected_workers


def test_concurrency_options_property_access():
    """Test that the concurrency_options property works correctly."""
    options = ConcurrencyOptions(
        maximum_concurrent_activity_work_items=15,
        maximum_concurrent_orchestration_work_items=25,
        maximum_thread_pool_workers=30,
    )

    worker = TaskHubGrpcWorker(concurrency_options=options)
    retrieved_options = worker.concurrency_options

    # Should be the same object
    assert retrieved_options is options

    # Should have correct values
    assert retrieved_options.maximum_concurrent_activity_work_items == 15
    assert retrieved_options.maximum_concurrent_orchestration_work_items == 25
    assert retrieved_options.maximum_thread_pool_workers == 30
