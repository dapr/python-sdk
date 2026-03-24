import asyncio
import threading
import time

from durabletask.worker import ConcurrencyOptions, TaskHubGrpcWorker


class DummyStub:
    def __init__(self):
        self.completed = []

    def CompleteOrchestratorTask(self, res):
        self.completed.append(("orchestrator", res))

    def CompleteActivityTask(self, res):
        self.completed.append(("activity", res))


class DummyRequest:
    def __init__(self, kind, instance_id):
        self.kind = kind
        self.instanceId = instance_id
        self.orchestrationInstance = type("O", (), {"instanceId": instance_id})
        self.name = "dummy"
        self.taskId = 1
        self.input = type("I", (), {"value": ""})
        self.pastEvents = []
        self.newEvents = []

    def HasField(self, field):
        return (field == "orchestratorRequest" and self.kind == "orchestrator") or (
            field == "activityRequest" and self.kind == "activity"
        )

    def WhichOneof(self, _):
        return f"{self.kind}Request"


class DummyCompletionToken:
    pass


def test_worker_concurrency_loop_sync():
    options = ConcurrencyOptions(
        maximum_concurrent_activity_work_items=2,
        maximum_concurrent_orchestration_work_items=1,
        maximum_thread_pool_workers=2,
    )
    worker = TaskHubGrpcWorker(concurrency_options=options)
    stub = DummyStub()

    def dummy_orchestrator(req, stub, completionToken):
        time.sleep(0.1)
        stub.CompleteOrchestratorTask("ok")

    def dummy_activity(req, stub, completionToken):
        time.sleep(0.1)
        stub.CompleteActivityTask("ok")

    # Patch the worker's _execute_orchestrator and _execute_activity
    worker._execute_orchestrator = dummy_orchestrator
    worker._execute_activity = dummy_activity

    orchestrator_requests = [DummyRequest("orchestrator", f"orch{i}") for i in range(3)]
    activity_requests = [DummyRequest("activity", f"act{i}") for i in range(4)]

    async def run_test():
        # Start the worker manager's run loop in the background
        worker_task = asyncio.create_task(worker._async_worker_manager.run())
        for req in orchestrator_requests:
            worker._async_worker_manager.submit_orchestration(
                dummy_orchestrator, req, stub, DummyCompletionToken()
            )
        for req in activity_requests:
            worker._async_worker_manager.submit_activity(
                dummy_activity, req, stub, DummyCompletionToken()
            )
        await asyncio.sleep(1.0)
        orchestrator_count = sum(1 for t, _ in stub.completed if t == "orchestrator")
        activity_count = sum(1 for t, _ in stub.completed if t == "activity")
        assert orchestrator_count == 3, (
            f"Expected 3 orchestrator completions, got {orchestrator_count}"
        )
        assert activity_count == 4, f"Expected 4 activity completions, got {activity_count}"
        worker._async_worker_manager._shutdown = True
        await worker_task

    asyncio.run(run_test())


# Dummy orchestrator and activity for sync context
def dummy_orchestrator(ctx, input):
    # Simulate some work
    time.sleep(0.1)
    return "orchestrator-done"


def dummy_activity(ctx, input):
    # Simulate some work
    time.sleep(0.1)
    return "activity-done"


def test_worker_concurrency_sync():
    # Use small concurrency to make test observable
    options = ConcurrencyOptions(
        maximum_concurrent_activity_work_items=2,
        maximum_concurrent_orchestration_work_items=2,
        maximum_thread_pool_workers=2,
    )
    worker = TaskHubGrpcWorker(concurrency_options=options)
    worker.add_orchestrator(dummy_orchestrator)
    worker.add_activity(dummy_activity)

    # Simulate submitting work items to the queues directly (bypassing gRPC)
    # We'll use the internal _async_worker_manager for this test
    manager = worker._async_worker_manager
    results = []
    lock = threading.Lock()

    def make_work(kind, idx):
        def fn(*args, **kwargs):
            time.sleep(0.1)
            with lock:
                results.append((kind, idx))
            return f"{kind}-{idx}-done"

        return fn

    # Submit more work than concurrency allows
    for i in range(5):
        manager.submit_orchestration(make_work("orch", i))
        manager.submit_activity(make_work("act", i))

    # Run the manager loop in a thread (sync context)
    def run_manager():
        asyncio.run(manager.run())

    t = threading.Thread(target=run_manager)
    t.start()
    time.sleep(1.5)  # Let work process
    manager.shutdown()
    # Unblock the consumers by putting dummy items in the queues
    manager.activity_queue.put_nowait((lambda: None, (), {}))
    manager.orchestration_queue.put_nowait((lambda: None, (), {}))
    t.join(timeout=2)

    # Check that all work items completed
    assert len(results) == 10
