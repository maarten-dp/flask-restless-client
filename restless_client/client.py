from .connection import Connection
from .property import LoadableProperty
from .filter import Query
from .utils import urljoin, State, get_depth, RelationHelper
from .collections import ObjectCollection, TypedList
from .marshal import ObjectDeserializer, ObjectSerializer
from .models import BaseObject
from .ext.auth import BaseSession, Session
from contextlib import contextmanager
import crayons
import logging
import sys
from itertools import chain


class DepthFilter(logging.Filter):
    def filter(self, record):
        record.depth = crayons.yellow('{}>'.format('-' * get_depth()), True, True)
        return True


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('restless-client')
logger.addFilter(DepthFilter())
steam_handler = logging.StreamHandler(sys.stdout)
steam_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(depth)s %(message)s')
steam_handler.setFormatter(formatter)
logger.addHandler(steam_handler)
logger.propagate = False


class Options:
    def __init__(self, opts):
        # the only entrypoint to load/save/update objects
        self.ConnectionClass = opts.pop('connection', Connection)
        # takes care of populating instances based on the given kwargs
        self.DeserializeClass = opts.pop('deserializer', ObjectDeserializer)
        self.SerializeClass = opts.pop('deserializer', ObjectSerializer)
        self.RelationHelper = opts.pop('relhelper', RelationHelper)
        # takes care of building the classes
        self.ConstructorClass = opts.pop('constructor', ClassConstructor)
        # base object every constructed class will inherit from
        self.BaseObject = opts.pop('base_object', BaseObject)
        # type of list used to group multiple objects when executing a query
        self.CollectionClass = opts.pop('collection_class', ObjectCollection)
        # type of list used to keep track of instance relations
        self.TypedListClass = opts.pop('typed_list', TypedList)
        # the property used by constructed classes to handle model attributes
        self.LoadableProperty = opts.pop('loadable_property', LoadableProperty)

        self.debug = opts.pop('debug', True)

        if 'session' in opts:
            self.session = opts.pop('session')
        else:
            auth_url = opts.pop('auth_url', urljoin(self.base_url, 'auth'))
            self.session = Session(auth_url, username, password, token, **opts)


class ClassConstructor:
    def __init__(self, client, opts):
        self.client = client
        self.opts = opts

    def construct_class(self, name, details):
        attributes = {
            '_client': self.client,
            '_class_name': name,
            '_pk_name': details['pk_name'],
            '_attrs': details['attributes'],
            '_relations': details['relations'],
            '_methods': details['methods'].keys(),
            '_base_url': urljoin(self.client.model_url, name.lower()),
            '_connection': self.client.connection,
            '_deserializer': self.client.deserializer,
            '_polymorphic': details.get('polymorphic', {}),
            '_relhelper': self.opts.RelationHelper(
                self.client, self.opts, details['relations'])
        }
        slots = []
        for field in chain(details['attributes'], details['relations']):
            attributes[field] = self.opts.LoadableProperty(field)
        # construct methods
        # for method, method_details in details['methods'].items():
        #     attributes[method] = create_method_function(
        #         self, method, method_details)

        inherits = [self.opts.BaseObject]
        if details.get('polymorphic', {}).get('parent'):
            parent = self.client._classes[details['polymorphic']['parent']]
            inherits.insert(0, parent)
        klass = type(str(name), tuple(inherits), attributes)
        klass.query = Query(self.client.connection, klass)
        self.client._classes[name] = klass
        setattr(self.client, name, klass)


class Client:
    def __init__(self, url, username=None, password=None, token=None, **kwargs):
        self.base_url = url
        self.state = State.LOADABLE
        self.model_url = kwargs.pop('model_root', url)
        if 'http' not in self.model_url:
            self.model_url = urljoin(url, self.model_url)

        self.registry = {}
        self._classes = {}

        self.opts = Options(kwargs)

        self.connection = self.opts.ConnectionClass(self, self.opts)
        self.serializer = self.opts.SerializeClass(self, self.opts)
        self.deserializer = self.opts.DeserializeClass(self, self.opts)
        self.constructor = self.opts.ConstructorClass(self, self.opts)

        self.initialize()

    def initialize(self):
        url = urljoin(self.base_url, 'restless-client-datamodel')
        res = self.connection.request(url)
        delayed = {}
        for name, details in res.items():
            if details.get('polymorphic', {}).get('parent'):
                delayed[name] = details
                continue
            self.constructor.construct_class(name, details)
        for name, details in delayed.items():
            self.constructor.construct_class(name, details)

    @property
    @contextmanager
    def loading(self):
        self.state = State.LOADING
        yield
        self.state = State.LOADABLE

    @property
    def is_loading(self):
        return self.state == State.LOADING

    def _register(self, obj):
        self.registry['%s%s' % (obj.__class__.__name__, obj._pkval)] = obj

    def save(self):
        for obj in self.registry.values():
            if obj._dirty:
                obj.save()
