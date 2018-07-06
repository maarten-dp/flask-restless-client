from cereal_lazer import serialize, deserialize
from itertools import permutations
import datetime
import pytz
import pytest


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
