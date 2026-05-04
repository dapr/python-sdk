import pytest

EXPECTED_LINES = [
    'Add 3 and 4.',
    '7',
    '14',
]


@pytest.mark.example_dir('langgraph-checkpointer')
def test_langgraph_checkpointer(dapr, ollama, flush_redis):
    output = dapr.run(
        '--app-id langgraph-checkpointer --dapr-grpc-port 5002 '
        '--resources-path ./components -- python3 agent.py',
        timeout=120,
    )
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'
