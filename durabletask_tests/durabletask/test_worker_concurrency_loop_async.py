import asyncio

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


def test_worker_concurrency_loop_async():
    options = ConcurrencyOptions(
        maximum_concurrent_activity_work_items=2,
        maximum_concurrent_orchestration_work_items=1,
        maximum_thread_pool_workers=2,
    )
    grpc_worker = TaskHubGrpcWorker(concurrency_options=options)
    stub = DummyStub()

    async def dummy_orchestrator(req, stub, completionToken):
        await asyncio.sleep(0.1)
        stub.CompleteOrchestratorTask("ok")

    async def dummy_activity(req, stub, completionToken):
        await asyncio.sleep(0.1)
        stub.CompleteActivityTask("ok")

    # Patch the worker's _execute_orchestrator and _execute_activity
    grpc_worker._execute_orchestrator = dummy_orchestrator
    grpc_worker._execute_activity = dummy_activity

    orchestrator_requests = [DummyRequest("orchestrator", f"orch{i}") for i in range(3)]
    activity_requests = [DummyRequest("activity", f"act{i}") for i in range(4)]

    async def run_test():
        # Clear stub state before each run
        stub.completed.clear()
        worker_task = asyncio.create_task(grpc_worker._async_worker_manager.run())
        for req in orchestrator_requests:
            grpc_worker._async_worker_manager.submit_orchestration(
                dummy_orchestrator, req, stub, DummyCompletionToken()
            )
        for req in activity_requests:
            grpc_worker._async_worker_manager.submit_activity(
                dummy_activity, req, stub, DummyCompletionToken()
            )
        await asyncio.sleep(1.0)
        orchestrator_count = sum(1 for t, _ in stub.completed if t == "orchestrator")
        activity_count = sum(1 for t, _ in stub.completed if t == "activity")
        assert orchestrator_count == 3, (
            f"Expected 3 orchestrator completions, got {orchestrator_count}"
        )
        assert activity_count == 4, f"Expected 4 activity completions, got {activity_count}"
        grpc_worker._async_worker_manager._shutdown = True
        await worker_task

    asyncio.run(run_test())
    asyncio.run(run_test())
