import pytest


@pytest.fixture(scope='module')
def client(dapr_env):
    return dapr_env.start_sidecar(app_id='test-metadata')


class TestGetMetadata:
    def test_application_id_matches(self, client):
        meta = client.get_metadata()
        assert meta.application_id == 'test-metadata'

    def test_registered_components_present(self, client):
        meta = client.get_metadata()
        component_types = {c.type for c in meta.registered_components}
        assert any(t.startswith('state.') for t in component_types)

    def test_registered_components_have_names(self, client):
        meta = client.get_metadata()
        for comp in meta.registered_components:
            assert comp.name
            assert comp.type


class TestSetMetadata:
    def test_set_and_get_roundtrip(self, client):
        client.set_metadata('test-key', 'test-value')
        meta = client.get_metadata()
        assert meta.extended_metadata.get('test-key') == 'test-value'

    def test_overwrite_existing_key(self, client):
        client.set_metadata('overwrite-key', 'first')
        client.set_metadata('overwrite-key', 'second')
        meta = client.get_metadata()
        assert meta.extended_metadata['overwrite-key'] == 'second'

    def test_empty_value_is_allowed(self, client):
        client.set_metadata('empty-key', '')
        meta = client.get_metadata()
        assert 'empty-key' in meta.extended_metadata
        assert meta.extended_metadata['empty-key'] == ''
