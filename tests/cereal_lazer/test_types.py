import pytz
import pytest
import datetime
from functools import partial
from webargs.fields import String
from itertools import permutations
from cereal_lazer import DynamicType, _deserialize
from cereal_lazer import serialize, deserialize, register_serializable_type


to_test = [
    ('<int|5|>', 5),
    ('<float|5.5|>', 5.5),
    ('<str|test|>', 'test'),
    ('<list|<int|1|>,<str|test|>,<float|6.7|>|>', [1, 'test', 6.7]),
    ('<tuple|<int|1|>,<str|test|>,<float|6.7|>|>', tuple([1, 'test', 6.7])),
    ('<dict|<str|test1|>:<float|5.5|>,<str|test2|>:<int|4|>,<int|6|>:<str|test3|>|>', {'test1': 5.5, 'test2': 4, 6: 'test3'}),
    ('<bool|True|>', True),
    ('<bool|False|>', False),
    ('<date|2018-01-01|>', datetime.date(2018, 1, 1)),
    ('<datetime|2018-01-01T00:00:00+00:00|>', datetime.datetime(2018, 1, 1, tzinfo=pytz.UTC)),
    ('<time|23:00:00|>', datetime.time(23, 0, 0)),
    ('<list|<int|1|>,<str|test|>,<list|<int|2|>,<str|test1|>|>|>', [1, 'test', [2, 'test1']]),
    ('<dict|<int|1|>:<str|test|>,<str|test|>:<dict|<int|2|>:<float|5.6|>|>,<int|3|>:<list|<int|1|>,<int|2|>|>|>', {1: 'test', 'test': {2: 5.6}, 3: [1, 2]})
]

@pytest.mark.parametrize('expected, to_serialize', to_test)
def test_serialize(expected, to_serialize):
    assert serialize(to_serialize) == expected


@pytest.mark.parametrize('to_deserialize,expected', to_test)
def test_deserialize(to_deserialize, expected):
    assert deserialize(to_deserialize) == expected


def test_serialize_set():
    items = ['<int|1|>', '<str|test|>', '<float|6.7|>']
    expected = []
    for permutation in permutations(items):
        expected.append('<set|{},{},{}|>'.format(*permutation))
    assert serialize(set([1, 'test', 6.7])) in expected

def test_deserialize_set():
    expected = '<set|<int|1|>,<str|test|>,<float|6.7|>|>'
    assert set([1, 'test', 6.7]) == deserialize(expected)


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

    class CustomType(String):
        def _deserialize(self, value, attr, data):
            args = [_deserialize(*v) for v in value]
            return SomeObject(*args)

        def _serialize(self, value, attr, obj):
            dt = DynamicType()
            c = partial(dt._serialize, attr=attr, obj=obj)
            return ','.join([c(value.a), c(value.wild), c(value.attribute)])

    register_serializable_type(SomeObject.__name__, CustomType)
    return SomeObject


def test_serialize_custom_type():
    obj = set_up_custom_type()
    o = obj(1, 'test', [5.5, True])
    expected = '<SomeObject|<int|1|>,<str|test|>,<list|<float|5.5|>,<bool|True|>|>|>'
    assert serialize(o) == expected


def test_deserialize_custom_type():
    obj = set_up_custom_type()
    expected = obj(1, 'test', [5.5, True])
    inp = '<SomeObject|<int|1|>,<str|test|>,<list|<float|5.5|>,<bool|True|>|>|>'
    assert deserialize(inp) == expected
