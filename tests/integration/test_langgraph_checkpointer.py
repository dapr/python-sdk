import subprocess
import time

import httpx
import pytest

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
    except httpx.RequestError:
        return False

    return any(m['name'] == MODEL for m in resp.json().get('models', []))


def _wait_for_ollama(timeout: float = 30.0, interval: float = 0.5) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _ollama_ready():
            return
        time.sleep(interval)
    raise TimeoutError(f'ollama serve did not become ready within {timeout}s')


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
        _wait_for_ollama()

    if not _model_available():
        subprocess.run(['ollama', 'pull', MODEL], check=True, capture_output=True)

    yield

    if started:
        started.terminate()
        started.wait(timeout=10)


@pytest.fixture()
def flush_redis():
    """This test is not replayable if the checkpointer state store is not clean."""
    subprocess.run(
        ['docker', 'exec', 'dapr_redis', 'redis-cli', 'FLUSHDB'],
        capture_output=True,
        check=True,
        timeout=10,
    )


@pytest.mark.example_dir('langgraph-checkpointer')
def test_langgraph_checkpointer(dapr, ollama, flush_redis):
    output = dapr.run(
        '--app-id langgraph-checkpointer --dapr-grpc-port 5002 '
        '--resources-path ./components -- python3 agent.py',
        timeout=120,
    )
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'
