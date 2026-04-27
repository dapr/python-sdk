import pytest


@pytest.fixture(scope='module')
def client(dapr_env, apps_dir):
    return dapr_env.start_sidecar(
        app_id='invoke-receiver',
        grpc_port=50001,
        app_port=50051,
        app_cmd=f'python3 {apps_dir / "invoke_receiver.py"}',
    )


def test_invoke_method_returns_expected_response(client):
    resp = client.invoke_method(
        app_id='invoke-receiver',
        method_name='my-method',
        data=b'{"id": 1, "message": "hello world"}',
        content_type='application/json',
    )
    # The app returns 'text/plain; charset=UTF-8', but Dapr may strip
    # parameters when proxying through gRPC, so only check the media type.
    assert resp.content_type.startswith('text/plain')
    assert resp.data == b'INVOKE_RECEIVED'


def test_invoke_method_with_text_data(client):
    resp = client.invoke_method(
        app_id='invoke-receiver',
        method_name='my-method',
        data=b'plain text',
        content_type='text/plain',
    )
    assert resp.data == b'INVOKE_RECEIVED'
