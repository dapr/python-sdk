import pytest

EXPECTED_LINES = [
    'First, we will assign a new custom label to Dapr sidecar',
    "Now, we will fetch the sidecar's metadata",
    'And this is what we got:',
    'application_id: my-metadata-app',
    'active_actors_count: {}',
    'registered_components:',
    'We will update our custom label value and check it was persisted',
    'We added a custom label named [is-this-our-metadata-example]',
]


@pytest.mark.example_dir('metadata')
def test_metadata(dapr):
    output = dapr.run(
        '--app-id=my-metadata-app --app-protocol grpc --resources-path components/ python3 app.py',
        timeout=10,
    )
    for line in EXPECTED_LINES:
        assert line in output, f'Missing in output: {line}'
