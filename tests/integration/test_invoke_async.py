import pytest

from dapr.aio.clients import DaprClient as AsyncDaprClient

GRPC_ADDRESS = '127.0.0.1:50001'


@pytest.fixture(scope='module')
def sidecar(dapr_env, apps_dir):
    dapr_env.start_sidecar(
        app_id='invoke-receiver-async',
        app_port=50051,
        app_cmd=f'python3 {apps_dir / "invoke_receiver.py"}',
    )


async def test_invoke_method_returns_expected_response(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        resp = await d.invoke_method(
            app_id='invoke-receiver-async',
            method_name='my-method',
            data=b'{"id": 1, "message": "async hello"}',
            content_type='application/json',
        )

    assert resp.content_type.startswith('text/plain')
    assert resp.data == b'INVOKE_RECEIVED'


async def test_invoke_method_with_text_data(sidecar):
    async with AsyncDaprClient(address=GRPC_ADDRESS) as d:
        resp = await d.invoke_method(
            app_id='invoke-receiver-async',
            method_name='my-method',
            data=b'plain text',
            content_type='text/plain',
        )

    assert resp.data == b'INVOKE_RECEIVED'
