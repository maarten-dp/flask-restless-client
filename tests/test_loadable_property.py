from unittest import mock

import pytest

from restless_client.filter import ComparisonResult
from restless_client.inspect import InstanceState, ModelMeta, inspect
from restless_client.property import FilterNode, LoadableProperty


@pytest.fixture
def Stub():
    client = mock.Mock(is_loading=False, connection=mock.Mock())

    class StubClass:
        _relations = {}
        oid = 1
        attribute1 = LoadableProperty('attribute1')
        _rlc = ModelMeta(client=client,
                         relations=[],
                         pk_name='oid',
                         class_name=None,
                         attributes=None,
                         properties=None,
                         methods=None,
                         base_url=None,
                         method_url=None,
                         property_url=None,
                         polymorphic=None,
                         relhelper=None)

        def __init__(self, **kwargs):
            self._rlc.client = kwargs.get('client', client)
            self._rlc = InstanceState(self)
            self._rlc.dirty = kwargs.get('dirty', set())
            self._rlc.values = kwargs.get('values', {})

    return StubClass


def test_it_can_set_an_attribute(Stub):
    stub = Stub()
    stub.attribute1 = 'test'
    assert stub.attribute1 == 'test'
    assert Stub().attribute1 != 'test'


def test_it_can_load_an_attribute(Stub):
    stub = Stub()
    assert stub.attribute1 == None
    inspect(stub).connection.load.assert_called_once()


def test_it_can_return_loaded_values(Stub):
    stub = Stub()
    inspect(stub).values['attribute1'] = 'test'
    assert stub.attribute1 == 'test'


def test_it_flags_attribute_as_dirty_when_set(Stub):
    stub = Stub()
    stub.attribute1 = 'test'
    assert 'attribute1' in inspect(stub).dirty


def test_it_does_not_update_when_dirty_and_loading(Stub):
    client = mock.Mock(is_loading=True)
    stub = Stub(client=client)
    inspect(stub).dirty.add('attribute1')
    inspect(stub).values['attribute1'] = 'test'
    stub.attribute1 = 'not test'
    assert stub.attribute1 == 'test'


def test_it_returns_a_filter_as_class_attribute(Stub):
    assert type(Stub.attribute1 == 1) == ComparisonResult


def test_is_returns_relation_property(Stub):
    client = mock.Mock(_classes={'SOMEMODEL': 'SOMEMODEL'})
    Stub._client = client
    inspect(Stub).relations = {
        'attribute1': {
            'relation_type': 'WHOTOCARES',
            'foreign_model': 'SOMEMODEL'
        }
    }
    assert type(Stub.attribute1) == FilterNode
