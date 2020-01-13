import pytest
from requests.exceptions import HTTPError

from restless_client.filter import FilterMixIn


def test_eq(fcl):
    o = fcl.Object1
    res = o.query.filter(o.attribute2 == 4).all()
    assert len(res) == 1
    assert res[0].id == 4 and res[0].attribute2 == 4


def test_ne(fcl):
    o = fcl.Object1
    res = o.query.filter(o.attribute2 != 4).all()
    assert len(res) == 4
    assert sorted([ob.id for ob in res]) == [1, 2, 3, 5]
    assert sorted([ob.attribute2 for ob in res]) == [1, 2, 3, 5]


def test_invert(fcl):
    o = fcl.Object1
    res = o.query.filter(~(o.attribute2 == 4)).all()
    assert len(res) == 4
    assert sorted([ob.id for ob in res]) == [1, 2, 3, 5]
    assert sorted([ob.attribute2 for ob in res]) == [1, 2, 3, 5]


def test_lt(fcl):
    o = fcl.Object1
    res = o.query.filter(o.attribute2 < 4).all()
    assert len(res) == 3
    assert sorted([ob.id for ob in res]) == [1, 2, 3]
    assert sorted([ob.attribute2 for ob in res]) == [1, 2, 3]


def test_lte(fcl):
    o = fcl.Object1
    res = o.query.filter(o.attribute2 <= 4).all()
    assert len(res) == 4
    assert sorted([ob.id for ob in res]) == [1, 2, 3, 4]
    assert sorted([ob.attribute2 for ob in res]) == [1, 2, 3, 4]


def test_gt(fcl):
    o = fcl.Object1
    res = o.query.filter(o.attribute2 > 4).all()
    assert len(res) == 1
    assert sorted([ob.id for ob in res]) == [5]
    assert sorted([ob.attribute2 for ob in res]) == [5]


def test_gte(fcl):
    o = fcl.Object1
    res = o.query.filter(o.attribute2 >= 4).all()
    assert len(res) == 2
    assert sorted([ob.id for ob in res]) == [4, 5]
    assert sorted([ob.attribute2 for ob in res]) == [4, 5]


def test_in(fcl):
    o = fcl.Object1
    res = o.query.filter(o.attribute2.in_([1, 2, 3])).all()
    assert len(res) == 3
    assert sorted([ob.id for ob in res]) == [1, 2, 3]
    assert sorted([ob.attribute2 for ob in res]) == [1, 2, 3]


def test_mix_of_things(fcl):
    o = fcl.Object1
    res = o.query.filter(o.attribute2.in_([2, 3, 4, 5]), o.id > 2,
                         o.id < 5).all()
    assert len(res) == 2
    assert sorted([ob.id for ob in res]) == [3, 4]
    assert sorted([ob.attribute2 for ob in res]) == [3, 4]


def test_single_fails_on_multi_result(fcl):
    o = fcl.Object1
    with pytest.raises(Exception):
        o.query.filter(o.attribute2.in_([1, 2, 3])).one()


def test_single(fcl):
    o = fcl.Object1
    res = o.query.filter(o.attribute2 == 4).one()
    assert res.id == 4 and res.attribute2 == 4


def test_one_or_none(fcl):
    o = fcl.Object1
    res = o.query.filter(o.attribute2 == 99).one_or_none()
    assert res == None


def test_one_or_none_fails_on_multiple(fcl):
    o = fcl.Object1
    with pytest.raises(Exception):
        o.query.filter(o.attribute2.in_([1, 2, 3])).one_or_none()


def test_filter_by(fcl):
    o = fcl.Object1
    res = o.query.filter_by(attribute2=4).all()
    assert len(res) == 1
    assert res[0].id == 4 and res[0].attribute2 == 4


def test_raw_filter():
    f = FilterMixIn()
    f.attribute = 'test'
    expected = {'name': 'test', 'op': '!=', 'val': 2}
    assert (~(f == 2)).to_raw_filter() == expected


def test_complex_filter():
    f = FilterMixIn()
    f.attribute = 'test'
    expected = {
        'or': [{
            'and': [{
                'name': 'test',
                'op': 'has',
                'val': {
                    'name': 'test',
                    'op': '==',
                    'val': 2
                }
            }, {
                'name': 'test',
                'op': 'not_in',
                'val': [1, 2, 3]
            }]
        }, {
            'name': 'test',
            'op': '>=',
            'val': 5
        }]
    }
    res = (f.has_((f == 2)) & (~f.in_([1, 2, 3])) | (f >= 5)).to_raw_filter()
    assert res == expected


def test_o2m_relation_filter(fcl):
    o = fcl.Object2
    f = o.relation1.relation2.attribute1 == "o3a11"
    expected = {
        'name': 'relation1',
        'op': 'has',
        'val': {
            'name': 'relation2',
            'op': 'has',
            'val': {
                'name': 'attribute1',
                'op': '==',
                'val': 'o3a11'
            }
        }
    }
    assert f.to_raw_filter() == expected


def test_m2o_relation_filter(fcl):
    o = fcl.Object3
    f = o.relation2.relation1.attribute1 == "o2a13"
    expected = {
        'name': 'relation2',
        'op': 'any',
        'val': {
            'name': 'relation1',
            'op': 'any',
            'val': {
                'name': 'attribute1',
                'op': '==',
                'val': 'o2a13'
            }
        }
    }
    assert f.to_raw_filter() == expected


def test_mix_relation_filter(fcl):
    o = fcl.Object1
    f = o.relation1.relation1.attribute1 == "o1a11"
    expected = {
        'name': 'relation1',
        'op': 'any',
        'val': {
            'name': 'relation1',
            'op': 'has',
            'val': {
                'name': 'attribute1',
                'op': '==',
                'val': 'o1a11'
            }
        }
    }
    assert f.to_raw_filter() == expected


def test_it_raises_an_error_on_unknown_attribute(fcl):
    with pytest.raises(AttributeError) as exc:
        assert fcl.Object1.relation1.Unknown == None


def test_filter_does_not_prevent_chaining_with_query(fcl):
    o = fcl.Object3
    oneobj = o.query.filter(o.attribute1 == "o3a11").one()
    assert isinstance(oneobj, o)

    allobjs = o.query.all()
    assert all([isinstance(obj, o) for obj in allobjs])
