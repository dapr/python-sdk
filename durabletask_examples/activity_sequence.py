"""End-to-end sample that demonstrates how to configure an orchestrator
that calls an activity function in a sequence and prints the outputs."""

from durabletask import client, task, worker


def hello(ctx: task.ActivityContext, name: str) -> str:
    """Activity function that returns a greeting"""
    return f"Hello {name}!"


def sequence(ctx: task.OrchestrationContext, _):
    """Orchestrator function that calls the 'hello' activity function in a sequence"""
    # call "hello" activity function in a sequence
    result1 = yield ctx.call_activity(hello, input="Tokyo")
    result2 = yield ctx.call_activity(hello, input="Seattle")
    result3 = yield ctx.call_activity(hello, input="London")

    # return an array of results
    return [result1, result2, result3]


# configure and start the worker
with worker.TaskHubGrpcWorker() as w:
    w.add_orchestrator(sequence)
    w.add_activity(hello)
    w.start()

    # create a client, start an orchestration, and wait for it to finish
    c = client.TaskHubGrpcClient()
    instance_id = c.schedule_new_orchestration(sequence)
    state = c.wait_for_orchestration_completion(instance_id, timeout=10)
    if state and state.runtime_status == client.OrchestrationStatus.COMPLETED:
        print(f"Orchestration completed! Result: {state.serialized_output}")
    elif state:
        print(f"Orchestration failed: {state.failure_details}")
