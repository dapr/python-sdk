import pytest

from tests.actor_grpc_utils import actor_stream_supported

DAPR_GRPC_PORT = 50061

EXPECTED_SERVICE = [
    'DemoActor is hosted over the Dapr gRPC actor stream',
    'Activate DemoActor actor!',
    'has_value: False',
    "set_my_data: {'data': 'new_data'}",
    'has_value: True',
    'set reminder to True',
    'set reminder is done',
    'set_timer to True',
    'set_timer is done',
    "receive_reminder is called - demo_reminder reminder - b'reminder_state'",
    'time_callback is called - timer_state',
    'clear_my_data',
]

EXPECTED_CLIENT = [
    'call actor method via proxy.invoke_method()',
    'null',
    'call actor method using rpc style',
    'None',
    'call SetMyData actor method to save the state',
    'call GetMyData actor method to get the state',
    'Register reminder',
    'Register timer',
    'stop reminder',
    'stop timer',
    'clear actor state',
]


@pytest.mark.example_dir('demo_actor/demo_actor')
def test_demo_actor_grpc(dapr):
    dapr.start(
        f'--app-id demo-actor --app-port 3001 --app-protocol grpc '
        f'--dapr-grpc-port {DAPR_GRPC_PORT} -- python3 demo_actor_grpc_service.py',
        wait=10,
    )
    if not actor_stream_supported(DAPR_GRPC_PORT):
        dapr.stop()
        pytest.skip('daprd does not support SubscribeActorEventsAlpha1')

    client_output = dapr.run(
        '--app-id demo-client -- python3 demo_actor_client.py',
        timeout=60,
    )
    for line in EXPECTED_CLIENT:
        assert line in client_output, f'Missing in client output: {line}'

    service_output = dapr.stop()
    for line in EXPECTED_SERVICE:
        assert line in service_output, f'Missing in service output: {line}'
