import logging
import sys
from itertools import chain

import crayons
from cereal_lazer import Cereal

from .collections import ObjectCollection, TypedList
from .connection import Connection
from .ext.auth import Session
from .filter import QueryFactory
from .inspect import ModelMeta
from .marshal import ObjectDeserializer, ObjectSerializer
from .method import Method, construct_method
from .models import BaseObject
from .property import LoadableProperty
from .utils import LoadingManager, RelationHelper, State, get_depth, urljoin


def register_serializer(model):
    rlc = model._rlc
    to_serialize = list(chain(rlc.attributes(), rlc.relations()))

    def load_model(value):
        return model(**value)

    def serialize_model(value):
        return rlc.serializer._raw_serialize(value, to_serialize)

    rlc.client.cereal.register_class(rlc.class_name, model, serialize_model,
                                     load_model)


class DepthFilter(logging.Filter):
    def filter(self, record):  # noqa A003
        record.depth = crayons.yellow('{}>'.format('-' * get_depth()), True,
                                      True)
        return True


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
        self.SerializeClass = opts.pop('serializer', ObjectSerializer)
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
        # how to reach the server when calling an object function
        self.Method = opts.pop('method_class', Method)
        self.ServerProperty = opts.pop('server_property_class', ServerProperty)

        self.debug = opts.pop('debug', True)
        self.data_model_endpoint = opts.pop('data_model_endpoint',
                                            'flask-restless-datamodel')

        # cereal lazer options
        # will return the raw data instead of raising an error when loading
        self.raise_load_errors = opts.pop('raise_load_errors', True)
        # will try to coerce non registered classes into an emulated object
        self.serialize_naively = opts.pop('serialize_naively', False)

        if 'session' in opts:
            self.session = opts.pop('session')
        else:
            auth_url = opts.pop('auth_url', urljoin(opts['base_url'], 'auth'))
            self.session = Session(auth_url, **opts)


class ServerProperty:
    def __init__(self, attribute, connection, base_url):
        self.attribute = attribute
        self.connection = connection
        self.url = '{}/property'.format(base_url)

    def __get__(self, obj, objtype=None):
        if objtype and obj is None:
            return self
        content = {'object': obj, 'property': self.attribute}
        payload = {'payload': self.cereal.dumps(content)}
        result = self.connection.request(self.url,
                                         http_method='post',
                                         json=payload)
        result = self.cereal.loads(result['payload'])
        return result

    @property
    def cereal(self):
        return self.connection.client.cereal


class ClassConstructor:
    def __init__(self, client, opts):
        self.client = client
        self.opts = opts

    def construct_class(self, name, details):
        meta = ModelMeta(client=self.client,
                         class_name=name,
                         pk_name=details['pk_name'],
                         attributes=details['attributes'],
                         properties=details['properties'],
                         relations=details['relations'],
                         methods=details['methods'].keys(),
                         base_url=urljoin(self.client.model_url,
                                          details['collection_name']),
                         method_url=urljoin(self.client.model_url, 'method',
                                            name.lower()),
                         polymorphic=details.get('polymorphic', {}),
                         relhelper=self.opts.RelationHelper(
                             self.client, self.opts, details['relations']))
        attributes = {'_rlc': meta}
        for field in chain(details['attributes'], details['relations']):
            attributes[field] = self.opts.LoadableProperty(field)

        for field in details['properties']:
            attributes[field] = self.opts.ServerProperty(
                field, self.client.connection, self.client.model_url)

        for method, method_details in details['methods'].items():
            attributes[method] = construct_method(self.opts, self.client,
                                                  method, method_details)

        inherits = [self.opts.BaseObject]
        if details.get('polymorphic', {}).get('parent'):
            parent = self.client._classes[details['polymorphic']['parent']]
            inherits.insert(0, parent)
        klass = type(str(name), tuple(inherits), attributes)
        klass.query = QueryFactory(self.client.connection, klass)
        self.client._classes[name] = klass
        setattr(self.client, name, klass)
        register_serializer(klass)


class Client:
    def __init__(self, url, **kwargs):
        self.base_url = url
        self.state = State.LOADABLE
        self.model_url = kwargs.pop('model_root', url)
        if 'http' not in self.model_url:
            self.model_url = urljoin(url, self.model_url)

        self.registry = {}
        self._classes = {}

        kwargs['base_url'] = url
        self.opts = Options(kwargs)

        self.connection = self.opts.ConnectionClass(self, self.opts)
        self.serializer = self.opts.SerializeClass(self, self.opts)
        self.deserializer = self.opts.DeserializeClass(self, self.opts)
        self.constructor = self.opts.ConstructorClass(self, self.opts)
        self.cereal = Cereal(
            serialize_naively=self.opts.serialize_naively,
            raise_load_errors=self.opts.raise_load_errors,
        )
        self.initialize()
        self.__loading_manager = LoadingManager(self)

    def initialize(self):
        url = urljoin(self.base_url, self.opts.data_model_endpoint)
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
    def loading(self):
        return self.__loading_manager

    @property
    def is_loading(self):
        return self.state == State.LOADING

    def _register(self, obj):
        self.registry['%s%s' % (obj.__class__.__name__, obj._rlc.pk_val)] = obj

    def delete(self, instance):
        instance._rlc.delete()

    def save(self, instance=None):
        if instance is None:
            for obj in self.registry.values():
                if obj._rlc.dirty:
                    obj._rlc.save()
        else:
            instance._rlc.save()
