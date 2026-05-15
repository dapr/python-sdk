import pytest

EXPECTED_LINES = [
    "Result: What's Dapr?",
    'Give a brief overview.',
]


@pytest.mark.example_dir('conversation')
def test_conversation_alpha1(dapr):
    output = dapr.run(
        '--app-id conversation-alpha1 --log-level debug --resources-path ./config '
        '-- python3 conversation_alpha1.py',
        timeout=60,
    )
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'


@pytest.mark.example_dir('conversation')
def test_conversation_alpha2(dapr):
    output = dapr.run(
        '--app-id conversation-alpha2 --log-level debug --resources-path ./config '
        '-- python3 conversation_alpha2.py',
        timeout=60,
    )
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'
