import bluesnake_client as client
from bluesnake_client import load_resource, parse_custom_types, BaseObject
from datetime import datetime
import requests
import pytest
from unittest.mock import Mock, ANY, patch
from dateutil import parser
import logging
from pytz import timezone, UTC
import pytz
from bluesnake_client import datetime_from_value, UserException
from collections import namedtuple

logger = logging.getLogger()

ORIG = client.load_resource
Result = namedtuple('Result', ['status_code', 'content', 'json', 'ok'])


def test_loadable_property():
    def mock_load_resource(session, url, *args, **kwargs):
        return {
            'attribute1': 'test1',
            'attribute2': 'test2',
            'relation1': {
                'id': 1,
                'attr1': 'test3'
            }
        }

    client.load_resource = mock_load_resource
    cl = client.Client(url='')

    class StubClass1(object):
        _attrs = {'attr1': ''}
        _base_url = ''
        _raw_data = {}

        def __init__(self, *args, **kwargs):
            for attr, val in kwargs.items():
                setattr(self, attr, val)

    class StubClass2(object):
        _attrs = {'attribute1': '', 'attribute2': ''}
        _relations = {'relation1': {'foreign_model': 'StubClass1'}}
        _base_url = ''
        _raw_data = {}
        id = 1
        attribute1 = client.loadable_property(cl, 'attribute1')
        attribute2 = client.loadable_property(cl, 'attribute2')
        relation1 = client.loadable_property(cl, 'relation1')

    cl._classes = {'StubClass1': StubClass1, 'StubClass2': StubClass2}

    stub = StubClass2()
    assert stub.attribute1 == 'test1'
    assert stub._attribute2 == 'test2'
    assert stub.relation1.__class__ == StubClass1
    assert stub.relation1.attr1 == 'test3'


def test_typed_list():
    class Stub1(object):
        pass

    lst = client.TypedList(Stub1, Stub1())
    with pytest.raises(Exception):
        lst.append(4)
    lst.append(Stub1())


def test_base_client():
    class Stub1():
        id = 4

    c = client.Client(url='')
    c._register(Stub1())
    assert c.registry.get('Stub14')


def test_client():
    class MockTokenRequest(object):
        status_code = 200
        ok = True

        def json(self):
            return {'access_token': ''}

    class MockClassRequest(object):
        status_code = 200
        ok = True

        def json(self, object_hook):
            return {}

    class MockSession(object):
        headers = {}

        def post(self, url, *args, **kwargs):
            return MockTokenRequest()

        def delete(self, url, *args, **kwargs):
            return MockTokenRequest()

        def get(self, url, *args, **kwargs):
            return MockClassRequest()

        def put(self, url, *args, **kwargs):
            return MockTokenRequest()

    client.load_resource = ORIG
    client.requests.Session = MockSession
    c = client.Client(url='', email='', password='')
    assert c._authenticated is True


def test_construct_class():
    objects = {
        'Object1': {
            'attributes': {
                'id': 'integer',
                'attribute1': 'string',
                'attribute2': 'integer',
            },
            'relations': {
                'relation1': {
                    'foreign_model': 'Object2',
                    'relation_type': 'o2m'
                },
            },
            'methods': {
                'method1': {
                    'args': ['arg1', 'arg2'],
                    'url': '{target}/{oid}/{method}{additional}'
                }
            }
        },
        'Object2': {
            'attributes': {
                'id': 'integer',
                'attribute1': 'string',
            },
            'relations': {},
            'methods': {}
        },
    }
    cl = client.Client(url='')
    for name, details in objects.items():
        cl._construct_class(name, details)
    assert len(cl._classes) == 2
    assert cl._classes.get('Object1')
    assert isinstance(cl.Object1.attribute1, property)
    assert isinstance(cl.Object1.relation1, property)
    assert cl._classes.get('Object2')

    assert sorted(cl.Object1.attrs()) == sorted(
        ['id', 'attribute1', 'attribute2'])
    assert sorted(cl.Object1.relations()) == sorted(['relation1'])
    assert sorted(cl.Object1.methods()) == sorted(['method1'])

    def mock_load_resource(session, url, *args, **kwargs):
        assert kwargs.get('testarg')
        assert url == '/object1/1/method1/rg1/rg2'
        return 'testvalue'

    client.load_resource = mock_load_resource
    inst = cl.Object1(id=1)
    assert hasattr(inst, 'method1')
    assert inst.method1(arg1='rg1', arg2='rg2', testarg='test') == 'testvalue'


def test_base_object_set_attr(cl):
    inst1 = cl.Object1(id=1, attribute1='test', attribute2=4, relation2=[])
    inst2 = cl.Object2(id=1, attribute1='test')

    assert inst1._dirty is False
    with pytest.raises(Exception):
        inst1.relation1 = 5
    inst1.relation1 = inst2
    assert inst1._dirty is True

    with pytest.raises(Exception):
        inst1.relation2.append(5)
    inst1.relation2.append(inst2)


def test_base_object_register(cl):
    inst1 = cl.Object1(id=1, attribute1='test', attribute2=4)
    inst2 = cl.Object1(id=1, attribute1='test')
    assert inst1 == inst2


def test_base_object_init(cl):
    inst1 = cl.Object1(id=1, attribute1='test', attribute2=4, relation2=[])
    assert inst1.id == 1
    assert inst1.attribute1 == 'test'
    assert inst1._attribute1 == 'test'
    assert isinstance(inst1.relation2, client.TypedList)


pprint = """idattribute1attribute2attribute3
1test152017-01-01
2test292017-01-01"""


def test_base_object_all(cl):
    def mock_load_resource(*args, as_timezone=None, **kwargs):
        args = args[1:]
        r = requests.Request('GET', *args, params=kwargs)
        prep = r.prepare()
        if prep.url == 'http://someurl.com/api/object1':
            return {
                'total_pages':
                2,
                'objects': [{
                    'id': 1,
                    'attribute1': 'test1',
                    'attribute2': 5,
                    'attribute3': '2017-01-01',
                    'relation1': {
                        'id': 1,
                        'attribute1': 'test3'
                    },
                    'relation2': [{
                        'id': 1,
                        'attribute1': 'test3'
                    }]
                }]
            }
        elif prep.url == 'http://someurl.com/api/object1?page=2':
            return {
                'total_pages':
                2,
                'objects': [{
                    'id': 2,
                    'attribute1': 'test2',
                    'attribute2': 9,
                    'attribute3': '2017-01-01',
                    'relation1': {
                        'id': 1,
                        'attribute1': 'test3'
                    },
                    'relation2': [{
                        'id': 1,
                        'attribute1': 'test3'
                    }]
                }]
            }

    client.load_resource = mock_load_resource
    objs = cl.Object1.all()
    assert len(objs) == 2
    assert len(cl.registry) == 3
    assert objs[0].id in (1, 2)
    assert 'test' in objs[0].attribute1
    assert objs.pprint().replace(" ", "") == pprint


def test_base_object_get(cl):
    def mock_load_resource(session, url, *args, **kwargs):
        return {
            'id': 1,
            'attribute1': 'test1',
            'attribute2': 5,
            'relation1': {
                'id': 1,
                'attribute1': 'test3'
            },
            'relation2': [{
                'id': 1,
                'attribute1': 'test3'
            }]
        }

    client.load_resource = mock_load_resource
    obj = cl.Object1.get(1)
    assert len(cl.registry) == 2
    assert obj.id == 1
    assert obj.attribute1 == 'test1'


def test_o2m_relation(cl):
    def mock_load_resource(session, url, *args, **kwargs):
        return {
            'id': 1,
            'attribute1': 'test',
            'relation1': {},
            'relation2': [{
                'id': 1,
                'attribute1': "rel2"
            }]
        }

    client.load_resource = mock_load_resource

    inst1 = cl.Object1(id=1, attribute1='test')
    assert inst1.relation2[0].attribute1 == 'rel2'


def test_create(cl):
    inst1 = cl.Object1(attribute3='2017-01-10')
    assert inst1.id == 'C1'


def test_repr(cl):
    inst1 = cl.Object1(id=1, attribute1='test')
    inst1.name = 'somename'
    assert str(inst1) == '<Object1 [id: 1 | name: somename]>'


def test_infer_date(cl):
    inst1 = cl.Object1(id=1, attribute3='2017-01-10')
    assert inst1.attribute3 == datetime(2017, 1, 10)


@patch('bluesnake_client.partial')
def test_load_resource_integrates_custom_object_hook(partial):
    session = Mock()
    response = session.get.return_value
    response.status_code = 200

    load_resource(session, ANY)

    response.json.assert_called_with(object_hook=partial.return_value)


@pytest.mark.parametrize('the_time', [
    '2017-04-26 16:11:54+00:00', '2017-04-26 16:11:54Z',
    '2017-04-26T16:11:54+00:00', '2017-04-26T16:11:54Z', '20170426T161154Z'
])
def test_parse_custom_types_converts_date_values_to_datetimes(the_time):
    result = parse_custom_types({'theTime': the_time})
    assert result['theTime'] == parser.parse(the_time)


def test_it_works_with_nested_datetimes():
    the_time = '20170426T161154Z'
    obj = {
        'asAttribute': the_time,
        'inList': [the_time],
        'nested': {
            'asAttribute': the_time,
            'inList': [the_time],
        },
        'withinList': [{
            'inObject': the_time
        }],
    }
    result = parse_custom_types(obj)

    the_datetime = parser.parse(the_time)
    assert result['asAttribute'] == the_datetime
    assert result['inList'][0] == the_datetime
    assert result['nested']['asAttribute'] == the_datetime
    assert result['nested']['inList'][0] == the_datetime
    assert result['withinList'][0]['inObject'] == the_datetime


def test_it_localizes_datetimes_if_provided_with_a_datetime():
    the_time = '20170426T161154Z'
    the_datetime = parser.parse(the_time)
    local_timezone = timezone('Australia/Sydney')

    result = datetime_from_value(the_time, local_timezone)

    assert str(the_datetime) == '2017-04-26 16:11:54+00:00'
    assert str(result) == '2017-04-27 02:11:54+10:00'


@patch('bluesnake_client.load_resource')
def test_the_client_uses_configured_timezone_for_response_parsing(
        load_resource):
    local_timezone = timezone('Australia/Sydney')

    objects = {
        'Any': {
            'attributes': {
                'id': 'integer',
            },
            'relations': {},
            'methods': {}
        },
    }
    cl = client.Client(url='')
    for name, details in objects.items():
        cl._construct_class(name, details)
    cl.timezone = local_timezone
    cl.Any.all()

    load_resource.assert_called_with(
        cl.session, '/any', as_timezone=local_timezone)


def test_it_uses_UTC_as_default_timezone():
    cl = client.Client(url='')
    assert cl.timezone == pytz.UTC


def test_it_allows_timezone_to_be_configured_as_timezone_object():
    cl = client.Client(url='')

    local_timezone = timezone('Australia/Sydney')
    cl.timezone = local_timezone

    assert cl.timezone == local_timezone


def test_it_allows_timezone_to_be_configured_as_timezone_name():
    cl = client.Client(url='')

    cl.timezone = 'Australia/Sydney'

    assert cl.timezone == timezone('Australia/Sydney')


def test_it_sets_timezone_to_UTC_if_set_to_None():
    cl = client.Client(url='')
    cl.timezone = 'Australia/Sydney'
    # pre-assertion
    assert cl.timezone != pytz.UTC

    cl.timezone = None
    assert cl.timezone == pytz.UTC


def test_it_can_be_constructed_with_a_custom_timezone():
    cl = client.Client(url='', timezone='Australia/Sydney')
    assert cl.timezone == timezone('Australia/Sydney')

    cl = client.Client(url='', timezone=timezone('Australia/Sydney'))
    assert cl.timezone == timezone('Australia/Sydney')


def test_can_save_object_with_attribute_fields():
    def post(url, json):
        expected = {
            "attribute1": "some_str",
            "attribute2": 3,
            "attribute3": False,
            "attribute4": 0
        }
        assert expected == json
        return Result(
            status_code=201, json=lambda: {'id': 1}, content=None, ok=True)

    objects = {
        'Object1': {
            'attributes': {
                'id': 'integer',
                'attribute1': 'string',
                'attribute2': 'integer',
                'attribute3': 'boolean',
                'attribute4': 'float',
                'attribute5': 'string'
            },
            'relations': {},
            'methods': {}
        },
    }
    cl = client.Client(url='')
    cl.session.post = post
    for name, details in objects.items():
        cl._construct_class(name, details)
    obj = cl.Object1(
        attribute1="some_str",
        attribute2=3,
        attribute3=False,
        attribute4=0.0,
        attribute5=None)
    assert obj.id == "C1"
    obj.save()
    assert obj.id == 1


def test_can_save_object_with_attribute_and_relation_fields():
    def post(url, json):
        return_id = 1
        if len(json) == 1:
            expected = {"attribute1": "some_str"}
        else:
            return_id = 2
            expected = {
                "attribute1": "some_str",
                "attribute2": 3,
                "relation1_id": 1
            }
        assert expected == json
        return Result(
            status_code=201,
            json=lambda: {'id': return_id},
            content=None,
            ok=True)

    objects = {
        'Object1': {
            'attributes': {
                'id': 'integer',
                'attribute1': 'string',
                'attribute2': 'integer',
            },
            'relations': {
                'relation1': {
                    'foreign_model': 'Object2',
                    'relation_type': 'o2m'
                },
            },
            'methods': {}
        },
        'Object2': {
            'attributes': {
                'id': 'integer',
                'attribute1': 'string',
            },
            'relations': {},
            'methods': {}
        },
    }
    cl = client.Client(url='')
    cl.session.post = post
    for name, details in objects.items():
        cl._construct_class(name, details)

    obj2 = cl.Object2(attribute1="some_str")
    obj1 = cl.Object1(attribute1="some_str", attribute2=3, relation1=obj2)
    assert obj2.id == "C1"
    assert obj1.id == "C2"
    obj1.save()
    assert obj2.id == 1
    assert obj1.id == 2


@pytest.fixture(scope='function')
def client_with_one_object():
    objects = {
        'Object1': {
            'attributes': {
                'id': 'integer',
                'attribute1': 'string',
                'attribute2': 'integer',
            },
            'relations': {},
            'methods': {}
        },
    }
    cl = client.Client(url='')

    for name, details in objects.items():
        cl._construct_class(name, details)

    return cl


def test_save_throws_error(client_with_one_object):
    cl = client_with_one_object

    def post(url, json):
        return Result(
            status_code=500, content="server error", json=None, ok=False)

    cl.session.post = post
    obj = cl.Object1(attribute1="some_str", attribute2=3)
    assert obj.id == "C1"
    with pytest.raises(Exception) as e:
        obj.save()
    msg = "Unable to create object Object1, recieved status code 500: server error"
    assert str(e.value) == msg


def test_update_object(client_with_one_object):
    cl = client_with_one_object

    obj = cl.Object1(attribute1="some_str", attribute2=3)
    with patch.object(cl.session, 'post') as post_mock:
        post_mock.return_value = Result(
            status_code=201, json=lambda: {'id': 1}, content=None, ok=True)
        obj.save()
        post_mock.assert_called_once_with(
            '/object1', json={
                'attribute1': "some_str",
                'attribute2': 3
            })

    obj.attribute1 = "some other string"
    obj.id = 1
    with patch.object(cl.session, 'put') as put_mock:
        put_mock.return_value = Result(
            status_code=200, json=lambda: {'id': 1}, content=None, ok=True)
        obj.save()
        put_mock.assert_called_once_with(
            '/object1/1',
            json={
                'attribute1': "some other string",
                'attribute2': 3
            })


def test_delete_object(client_with_one_object):
    cl = client_with_one_object

    obj = cl.Object1(attribute1="some_str", attribute2=3)
    obj.id = 1
    with patch.object(cl.session, 'delete') as delete_mock:
        delete_mock.return_value = Result(
            status_code=204, json=lambda: {'id': 1}, content=None, ok=True)
        obj.delete()
        delete_mock.assert_called_once_with('/object1/1')


def test_append_object_to_m2o_relation_sets_object_to_parent_backref(
        backref_cl):
    o1 = backref_cl.Object1()
    o2 = backref_cl.Object2()
    o1.relation1.append(o2)
    assert o2.relation1 == o1


def test_append_object_to_m2o_relation_appends_object_to_parent_backref(
        backref_cl):
    o1 = backref_cl.Object1()
    o2 = backref_cl.Object2()
    o1.relation2.append(o2)
    assert o1 in o2.relation2


def test_remove_object_in_m2o_relation_sets_object_to_parent_backref_to_none(
        backref_cl):
    o1 = backref_cl.Object1()
    o2 = backref_cl.Object2()
    o1.relation1.append(o2)
    assert o2.relation1 == o1
    o1.relation1.remove(o2)
    assert o2.relation1 is None


def test_appending_the_same_object_to_a_relation_throws_an_error(backref_cl):
    o1 = backref_cl.Object1()
    o2 = backref_cl.Object2()
    o1.relation2.append(o2)
    with pytest.raises(UserException):
        o1.relation2.append(o2)


@patch('bluesnake_client.load_resource')
def test_refresh(load_resource):
    def mock_load_resource1(session, url, *args, **kwargs):
        return {'attribute1': 'test2', 'attribute2': 'test3'}

    def mock_load_resource2(session, url, *args, **kwargs):
        return {'attribute1': 'test5', 'attribute2': 'test6'}

    load_resource.side_effect = mock_load_resource1
    cl = client.Client(url='')

    class StubClass2(client.BaseObject):
        _attrs = {'attribute1': '', 'attribute2': ''}
        _relations = {}
        _base_url = ''
        _parent = cl
        id = 1
        attribute1 = client.loadable_property(cl, 'attribute1')
        attribute2 = client.loadable_property(cl, 'attribute2')

    cl._classes = {'StubClass2': StubClass2}

    stub = StubClass2()
    assert stub.attribute1 == 'test2'
    assert stub._attribute2 == 'test3'

    load_resource.side_effect = mock_load_resource2
    stub.refresh()
    assert stub.attribute1 == 'test5'
    assert stub._attribute2 == 'test6'


@patch('bluesnake_client.load_resource')
def test_get_uses_cache(load_resource, cl):
    def mock_load_resource(session, url, *args, **kwargs):
        return {
            'id': 1,
            'attribute1': 'test1',
        }

    def mock_load_resource_raise(session, url, *args, **kwargs):
        raise Exception("Should not be raised, should be using cache")

    load_resource.side_effect = mock_load_resource
    obj = cl.Object1.get(1)
    assert obj.attribute1 == 'test1'
    load_resource.side_effect = mock_load_resource_raise
    assert obj == cl.Object1.get(1)


@patch('bluesnake_client.load_resource')
def test_detect_bulk_load(load_resource, cl):
    load_resource.return_value = {
        'objects': [{
            'id': 1
        }, {
            'id': 2
        }, {
            'id': 3
        }, {
            'id': 4
        }, {
            'id': 5
        }, {
            'id': 6
        }],
        'total_pages':
        1
    }
    objs = cl.Object1.filter(('attribute1', '==', 'somegenericname'))

    def mock_load(session, url, *args, **kwargs):
        if 'q' in kwargs:
            return {
                'objects': [{
                    'id': 1,
                    'relation1': {
                        'id': 1
                    }
                }, {
                    'id': 2,
                    'relation1': {
                        'id': 1
                    }
                }, {
                    'id': 3,
                    'relation1': {
                        'id': 1
                    }
                }, {
                    'id': 4,
                    'relation1': {
                        'id': 1
                    }
                }, {
                    'id': 5,
                    'relation1': {
                        'id': 1
                    }
                }, {
                    'id': 6,
                    'relation1': {
                        'id': 1
                    }
                }],
                'total_pages':
                1
            }
        else:
            oid = url[-1]
            return {'id': oid, 'relation1': {'id': 1}}

    load_resource.side_effect = mock_load
    for o in objs:
        o.relation1
    # assert 5 calls
    # 1 initial filter for somegenericname
    # 3 normal http calls
    # 1 triggered bulk load
    assert len(load_resource.mock_calls) == 5
    assert load_resource.mock_calls[-1].assert_called_with(
        None,
        'http://someurl.com/api/object1',
        as_timezone=UTC,
        q='{"filters": [{"op": "in", "name": "id", "val": [1, 2, 3, 4, 5, 6]}]}'
    )


@patch('bluesnake_client.BaseObject.filter')
def test_bulk_load_chunk(cls_filter, cl):
    parent = Mock(_bulk_load_chunk_size=50)
    BaseObject._parent = parent
    BaseObject.bulk_load(range(231))
    assert len(cls_filter.mock_calls) == 5
    assert cls_filter.mock_calls[0].assert_called_with(('id', 'in',
                                                        list(range(50))))
