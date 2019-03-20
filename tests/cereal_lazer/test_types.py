import pytz
import pytest
import datetime
from functools import partial
from itertools import permutations
from cereal_lazer import dumps, loads, register_class


to_test = [
    5,
    5.5,
    'test',
    [1, 'test', 6.7],
    {'test1': 5.5, 'test2': 4, 6: 'test3'},
    True,
    False,
    datetime.date(2018, 1, 1),
    datetime.datetime(2018, 1, 1, tzinfo=pytz.UTC),
    datetime.datetime(2018, 1, 1),
    [1, 2, 3, 4, 5],
    [1, 'test', [2, 'test,1']],
    {1: 'test', 'test': {2: 5.6}, 3: [1, 2]}
]

@pytest.mark.parametrize('to_serialize', to_test)
def test_serialize(to_serialize):
    assert loads(dumps(to_serialize, fmt='msgpack'), fmt='msgpack') == to_serialize


def set_up_custom_type():
    class SomeObject:
        def __init__(self, a, wild, attribute):
            self.a = a
            self.wild = wild
            self.attribute = attribute

        def __eq__(self, other):
            c1 = self.a == other.a
            c2 = self.wild == other.wild
            c3 = self.attribute == other.attribute
            return c1 and c2 and c3

    def to_builtin(v):
        return (v.a, v.wild, v.attribute)

    def from_builtin(v):
        return SomeObject(v[0], v[1], v[2])

    register_class(SomeObject.__name__, SomeObject, to_builtin, from_builtin)
    return SomeObject


def test_serialize_custom_type():
    obj = set_up_custom_type()
    o = obj(1, 'test', [5.5, True])
    assert loads(dumps(o, fmt='msgpack'), fmt='msgpack') == o
