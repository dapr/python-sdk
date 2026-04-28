import subprocess

import httpx
import pytest

from tests.wait_utils import wait_until

OLLAMA_URL = 'http://localhost:11434'
MODEL = 'llama3.2:latest'

EXPECTED_LINES = [
    'Add 3 and 4.',
    '7',
    '14',
]


def _ollama_ready() -> bool:
    try:
        return httpx.get(f'{OLLAMA_URL}/api/tags', timeout=2).is_success
    except httpx.RequestError:
        return False


def _model_available() -> bool:
    try:
        resp = httpx.get(f'{OLLAMA_URL}/api/tags', timeout=5)
        resp.raise_for_status()
    except httpx.RequestError:
        return False

    return any(m['name'] == MODEL for m in resp.json().get('models', []))


@pytest.fixture()
def ollama():
    """Ensure Ollama is running and the required model is pulled.

    Reuses a running instance if available, otherwise starts one for
    the duration of the test. Skips if the ollama CLI is not installed.
    """
    started: subprocess.Popen[bytes] | None = None
    if not _ollama_ready():
        try:
            started = subprocess.Popen(
                ['ollama', 'serve'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            pytest.skip('ollama is not installed')
        wait_until(_ollama_ready, timeout=30.0, interval=0.5)

    if not _model_available():
        subprocess.run(['ollama', 'pull', MODEL], check=True, capture_output=True)

    yield

    if started:
        started.terminate()
        started.wait(timeout=10)


@pytest.mark.example_dir('langgraph-checkpointer')
def test_langgraph_checkpointer(dapr, ollama, flush_redis):
    output = dapr.run(
        '--app-id langgraph-checkpointer --dapr-grpc-port 5002 '
        '--resources-path ./components -- python3 agent.py',
        timeout=120,
    )
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'
