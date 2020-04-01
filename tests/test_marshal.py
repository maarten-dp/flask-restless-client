from datetime import datetime
from unittest.mock import Mock

import pytest

from restless_client.inspect import inspect
from restless_client.marshal import ObjectDeserializer, ObjectSerializer
from restless_client.models import BaseObject


class TypedList(list):
    def __init__(self, otype, parent, for_attr=None, *args, **kwargs):
        self.type = otype
        self.parent = parent
        self.for_attr = for_attr
        super().__init__(*args, **kwargs)


@pytest.fixture
def ds():
    return ObjectDeserializer(
        Mock(), Mock(
            TypedListClass=TypedList,
            BaseObject=Mock,
        ))


@pytest.fixture
def s():
    return ObjectSerializer(Mock(), Mock(BaseObject=Mock))


def test_it_can_deserialize_an_attribute(ds):
    expected = {
        'attr1': 'val1',
        'attr2': 'val2',
    }
    obj = Mock(_rlc=Mock(_attributes=expected))
    ds.handle_attributes(obj, expected)
    assert obj.attr1 == 'val1'
    assert obj.attr2 == 'val2'


def test_it_can_deserialize_a_o2m_relation(ds):
    obj = Mock()
    reldef = [{'id': 1, 'attr1': 'someattr'}]
    ds.handle_o2m(obj, 'rel1', reldef, Mock)
    assert obj.rel1[0].id == 1
    assert obj.rel1[0].attr1 == 'someattr'


def test_it_can_deserialize_a_m2o_relation(ds):
    obj = Mock()
    reldef = {'id': 1, 'attr1': 'someattr'}
    ds.handle_m2o(obj, 'rel1', reldef, Mock)
    assert obj.rel1.id == 1
    assert obj.rel1.attr1 == 'someattr'


def test_it_can_deserialize_a_o2o_relation(ds):
    obj = Mock()
    reldef = {'id': 1, 'attr1': 'someattr'}
    ds.handle_o2o(obj, 'rel1', reldef, Mock)
    assert obj.rel1.id == 1
    assert obj.rel1.attr1 == 'someattr'


def setup_obj():
    relhelper = Mock()
    relhelper.column_name.side_effect = lambda x: x
    rlc = Mock(pk_name='id',
               relhelper=relhelper,
               values={
                   'id': 1,
                   'attr1': 'someattr',
                   'somedate': datetime(2018, 1, 1),
                   'somelist': [1, 2, 3],
                   'rel1': Mock(_rlc=Mock(pk_val=2, pk_name='id')),
                   'rel2': [Mock(_rlc=Mock(pk_val=3, pk_name='id'))],
               })
    obj = Mock(_rlc=rlc)
    rlc.attributes.return_value = ['id', 'attr1', 'somedate', 'somelist']
    rlc.relations.return_value = ['rel1', 'rel2']
    return obj


def test_it_can_serialize_an_object(s):
    obj = setup_obj()
    obj._dirty = set(['attr1', 'rel1'])
    result = s.serialize(obj)
    assert result == {
        'attr1': 'someattr',
        'somedate': '2018-01-01T00:00:00',
        'somelist': [1, 2, 3],
        'rel1': {
            'id': 2
        },
        'rel2': [{
            'id': 3
        }]
    }


def test_it_can_serialize_a_dirty_object(s):
    obj = setup_obj()
    obj._rlc.dirty = set(['attr1', 'rel1'])
    result = s.serialize_dirty(obj)
    assert result == {'attr1': 'someattr', 'rel1': {'id': 2}}
