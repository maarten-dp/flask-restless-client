from bluesnake_client.connection import AuthedSession, ObjectLoader, LoadableProperty
from bluesnake_client.utils import urljoin, State, get_depth
from bluesnake_client.models import BaseObject, create_method_function
from contextlib import contextmanager
import crayons
import logging
import sys


class DepthFilter(logging.Filter):
    def filter(self, record):
        record.depth = crayons.yellow('{}>'.format('-' * get_depth()), True, True)
        return True


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('bluesnake-client')
logger.addFilter(DepthFilter())
steam_handler = logging.StreamHandler(sys.stdout)
steam_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(depth)s %(message)s')
steam_handler.setFormatter(formatter)
logger.addHandler(steam_handler)


class Client:
    def __init__(self, url, username=None, password=None, token=None, **kwargs):
        self.base_url = url
        self.state = State.LOADABLE
        self.model_url = kwargs.pop('model_root', url)
        if 'http' not in self.model_url:
            self.model_url = urljoin(url, self.model_url)

        self.registry = {}
        self._classes = {}

        if 'session' in kwargs:
            self._session = kwargs['session']
        else:
            auth_url = urljoin(self.base_url, 'auth')
            self._session = AuthedSession(auth_url, username, password, token, **kwargs)

        self.object_loader = ObjectLoader(self._session)
        self.initialize()

    def initialize(self):
        res = self.object_loader.load_raw(urljoin(self.base_url, 'datamodel'))
        for name, details in res.items():
            self._construct_class(name, details)

    def _construct_class(self, name, details):
        attributes = {
            '_parent': self,
            '_class_name': name,
            '_attrs': details['attributes'],
            '_relations': details['relations'],
            '_methods': details['methods'].keys(),
            '_base_url': urljoin(self.model_url, name.lower()),
        }
        for field in details['attributes']:
            attributes[field] = LoadableProperty(field)
        for field in details['relations']:
            attributes[field] = LoadableProperty(field)
        # construct methods
        for method, method_details in details['methods'].items():
            attributes[method] = create_method_function(
                self, method, method_details)

        klass = type(str(name), (BaseObject, ), attributes)
        self._classes[name] = klass
        setattr(self, name, klass)

    @property
    @contextmanager
    def loading(self):
        if self.state == State.LOADING:
            raise Exception('Already in load state')
        self.state = State.LOADING
        yield
        self.state = State.LOADABLE

    def _register(self, obj):
        self.registry['%s%s' % (obj.__class__.__name__, obj.id)] = obj

    def save(self):
        for obj in self.registry.values():
            if obj._dirty:
                obj.save()
