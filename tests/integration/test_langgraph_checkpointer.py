import pytest

EXPECTED_LINES = [
    'Add 3 and 4.',
    '7',
    '14',
]


@pytest.mark.example_dir('langgraph-checkpointer')
def test_langgraph_checkpointer(dapr):
    proc = dapr.start(
        '--app-id langgraph-checkpointer --app-port 5001 --dapr-grpc-port 5002 '
        '--resources-path ./components -- python3 agent.py',
        wait=15,
    )
    output = dapr.stop(proc)
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'
