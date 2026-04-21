import pytest

EXPECTED_SERVICE = [
    'Activate DemoActor actor!',
    'has_value: False',
    "set_my_data: {'data': 'new_data'}",
    'has_value: True',
    'set reminder to True',
    'set reminder is done',
    'set_timer to True',
    'set_timer is done',
    'clear_my_data',
]

EXPECTED_CLIENT = [
    'call actor method via proxy.invoke_method()',
    "b'null'",
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
def test_demo_actor(dapr):
    dapr.start(
        '--app-id demo-actor --app-port 3000 -- uvicorn --port 3000 demo_actor_service:app',
        wait=10,
    )
    client_output = dapr.run(
        '--app-id demo-client python3 demo_actor_client.py',
        timeout=60,
    )
    for line in EXPECTED_CLIENT:
        assert line in client_output, f'Missing in client output: {line}'

    service_output = dapr.stop()
    for line in EXPECTED_SERVICE:
        assert line in service_output, f'Missing in service output: {line}'
