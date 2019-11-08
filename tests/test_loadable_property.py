from unittest import mock

import pytest

from restless_client.filter import ComparisonResult
from restless_client.property import FilterNode, LoadableProperty


@pytest.fixture
def Stub():
    client = mock.Mock(is_loading=False)

    class StubClass:
        _relations = {}
        attribute1 = LoadableProperty('attribute1')

        def __init__(self, **kwargs):
            self._pkval = 1
            self._dirty = kwargs.get('dirty', set())
            self._values = kwargs.get('values', {})
            self._relations = kwargs.get('relations', [])
            self._connection = mock.Mock()
            self._client = kwargs.get('client', client)
            self.is_new = kwargs.get('is_new', False)

    return StubClass


def test_it_can_set_an_attribute(Stub):
    stub = Stub()
    stub.attribute1 = 'test'
    assert stub.attribute1 == 'test'
    assert Stub().attribute1 != 'test'


def test_it_can_load_an_attribute(Stub):
    stub = Stub()
    assert stub.attribute1 == None
    stub._connection.load.assert_called_once()


def test_it_can_return_loaded_values(Stub):
    stub = Stub()
    stub._values['attribute1'] = 'test'
    assert stub.attribute1 == 'test'


def test_it_flags_attribute_as_dirty_when_set(Stub):
    stub = Stub()
    stub.attribute1 = 'test'
    assert 'attribute1' in stub._dirty


def test_it_does_not_update_when_dirty_and_loading(Stub):
    client = mock.Mock(is_loading=True)
    stub = Stub(client=client)
    stub._dirty.add('attribute1')
    stub._values['attribute1'] = 'test'
    stub.attribute1 = 'not test'
    assert stub.attribute1 == 'test'


def test_it_returns_a_filter_as_class_attribute(Stub):
    assert type(Stub.attribute1 == 1) == ComparisonResult


def test_is_returns_relation_property(Stub):
    client = mock.Mock(_classes={'SOMEMODEL': 'SOMEMODEL'})
    Stub._client = client
    Stub._relations = {
        'attribute1': {
            'relation_type': 'WHOTOCARES',
            'foreign_model': 'SOMEMODEL'
        }
    }
    assert type(Stub.attribute1) == FilterNode
