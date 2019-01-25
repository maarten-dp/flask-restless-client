éimport pytest
# from bluesnake_client import Client
from bluesnake_client.connection import AuthedSession
from bluesnake_client.client import Client
from requests.exceptions import HTTPError
from collections import defaultdict
import json
import copy
import os

ROOT = os.path.abspath(os.path.dirname(__file__))
DATAMODEL = json.load(open(os.path.join(ROOT, 'data', 'datamodel.json'), 'r'))
DB = json.load(open(os.path.join(ROOT, 'data', 'db.json'), 'r'))


def prepare(res):
    return {
        "num_results": len(res),
        "total_pages": 1,
        "page": 1,
        "objects": res
    }


def apply_filter(klass, args, db):
    operations = {
        '==': '__eq__',
        '!=': '__ne__',
        '>': '__gt__',
        '>=': '__ge__',
        '<': '__lt__',
        '<=': '__le__',
        'in': '__contains__',
    }
    objs = db[klass]
    for ofilter in args.get('filters', []):
        rset = []
        for obj in objs:
            expected = ofilter['val']
            to_check = obj[ofilter['name']]
            if ofilter['op'] == 'in':
                expected = obj[ofilter['name']]
                to_check = ofilter['val']
            comparator = getattr(to_check, operations[ofilter['op']])
            if comparator(expected):
                rset.append(obj)
        objs = rset
    if 'single' in args:
        if len(rset) > 1:
            return MockResponse({"message": "Multiple results found"}, 400)
        elif len(rset) < 1:
            return MockResponse({"message": "No result found"}, 404)
        else:
            return MockResponse(rset[0])
    if 'offset' in args:
        rset = rset[args['offset']:]
    if 'limit' in args:
        rset = rset[:args['limit']]
    if 'order_by' in args:
        rset = sorted(rset, key=lambda x: x[args['order_by']])
    return MockResponse(prepare(rset))


class MockResponse:
    def __init__(self, value, error=None):
        self.value = value
        self._reason = None
        self.error = error

    def json(self, *args, **kwargs):
        return self.value

    @property
    def content(self):
        return self.value

    @property
    def reason(self):
        return self._reason or self.value

    @reason.setter
    def reason(self, val):
        self._reason = val

    def raise_for_status(self, *args, **kwargs):
        if self.error:
            raise HTTPError(self.error, response=self)


class TestSession(AuthedSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = copy.deepcopy(DB)
        self.called = defaultdict(lambda: 0)

    def request(self, method, url, *args, **kwargs):
        methods = {
            'get': self._get_result
        }
        return self.validate_response(methods[method.lower()](url, *args, **kwargs))

    def _get_result(self, url, *args, **kwargs):
        if url.endswith('/auth'):
            return MockResponse({'access_token': ''})
        if 'datamodel' in url:
            return MockResponse(DATAMODEL)

        self.called['get'] += 1
        params = kwargs.get('params')
        for klass in ('Object1', 'Object2', 'Object3'):
            if klass.lower() not in url:
                continue
            if url.endswith(klass.lower()):
                if not params:
                    return MockResponse(prepare(self.db[klass]))
                else:
                    return apply_filter(klass, params['q'], self.db)
            else:
                try:
                    oid = int(url.split("/")[-1])
                except Exception:
                    continue
                for obj in self.db[klass]:
                    if obj['id'] == oid:
                        return MockResponse(obj)


@pytest.fixture(scope='function')
def session():
    return TestSession('http://myinstance.com/api', '', '')


@pytest.fixture(scope='function')
def cl(session):
    return Client(url='http://myinstance.com/api', session=session, debug=True)
