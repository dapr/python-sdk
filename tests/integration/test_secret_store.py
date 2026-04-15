import pytest

STORE = 'localsecretstore'


@pytest.fixture(scope='module')
def client(dapr_env, components_dir):
    return dapr_env.start_sidecar(app_id='test-secret', components=components_dir)


def test_get_secret(client):
    resp = client.get_secret(store_name=STORE, key='secretKey')
    assert resp.secret == {'secretKey': 'secretValue'}


def test_get_bulk_secret(client):
    resp = client.get_bulk_secret(store_name=STORE)
    assert 'secretKey' in resp.secrets
    assert resp.secrets['secretKey'] == {'secretKey': 'secretValue'}
