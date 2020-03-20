from collections import namedtuple

import pytest

from restless_client.connection import Connection
from restless_client.filter import Query
from restless_client.inspect import inspect


class Meta:
    def __init__(self, base_url, pk_name, client):
        self.base_url = base_url
        self.pk_name = pk_name
        self.client = client


class BaseObject:
    _rlc = Meta(
        base_url="http://app/api/formicarium",
        pk_name="id",
        client=None,
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class CollectionClass(list):
    def __init__(self, collection_class, objs):
        super().__init__(objs)


@pytest.fixture
def query(cl):
    cl.opts.CollectionClass = CollectionClass
    inspect(BaseObject).client = cl
    return Query(Connection(cl.opts.session, cl.opts), BaseObject)


def test_it_can_perform_an_all(query):
    result = query.all()
    assert len(result) == 5


def test_it_can_perform_an_all_on_several_pages(session, instances, query):
    for i in range(100):
        session.add(instances.Formicarium(name=f"MrNobody{i}"))
    session.commit()
    result = query.all()
    assert len(result) == 105


def test_it_can_perform_a_filter(query, cl):
    expected = 'Specimen-1'
    result = query.filter(cl.Formicarium.name == expected).one()
    assert result.name == expected


def test_it_can_perform_a_filter_by(query, cl):
    expected = 'Specimen-1'
    query.cls.name = cl.Formicarium.name
    result = query.filter_by(name=expected).one()
    assert result.name == expected


def test_it_can_perform_a_limit(query):
    result = query.limit(3).all()
    assert len(result) == 3


def test_it_can_perform_an_offset(query):
    result = query.offset(2).all()
    assert len(result) == 3


def test_it_can_perform_an_order_by_asc(query):
    result = query.order_by(name='asc').all()
    assert result[0].name == 'PAnts'


def test_it_can_perform_an_order_by_desc(query):
    result = query.order_by(name='desc').all()
    assert result[0].name == 'The yard yokels'


def test_it_can_perform_a_first(query):
    result = query.first()
    assert result.name == 'Specimen-1'


def test_it_can_perform_a_last(query):
    result = query.last()
    assert result.name == 'The Free SociAnty'


def test_it_can_perform_a_one_or_none_and_returns_none(query, cl):
    result = query.filter(
        cl.Formicarium.name == 'does not exist').one_or_none()
    assert result is None


def test_it_throws_an_error_when_one_or_none_returns_multiple_instances(query):
    with pytest.raises(Exception):
        query.one_or_none()


def test_it_can_perform_a_get(query):
    result = query.get(1)
    assert result.id == 1


def test_query_does_not_set_attributs_as_dirty(fcl):
    o = fcl.Object3
    results = o.query.all()
    assert not any([inspect(res).dirty for res in results])


def test_chaining_query_with_filter_does_not_have_side_effects(fcl):
    o = fcl.Object1
    objects = o.query.all()
    assert len(objects) == 5
    assert len(o.query.filter(o.attribute1 == "o1a11").all()) == 1
    assert len(o.query.all()) == 5
