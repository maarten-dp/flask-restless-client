from restless_client.filter import Query
from restless_client.property import LoadableProperty
from restless_client.utils import (urljoin, generate_id, classproperty, State,
    pretty_logger, TypedList, rel_info)
import logging
import crayons
from itertools import chain

logger = logging.getLogger('restless-client')
LOAD_MSG = 'loading {}.{} with value {}'


def log(o, a, v, attr_color='red'):
    logger.info(LOAD_MSG.format(
        crayons.yellow(o.__class__.__name__, always=True, bold=True),
        getattr(crayons, attr_color)(a, always=True, bold=True),
        crayons.green(str(v)[:150], always=True, bold=True)))


def log_loading(color):
    def decorator(fn):
        def execute(self, obj, field, val, *args, **kwargs):
            log(obj, field, val, color)
            return fn(self, obj, field, val, *args, **kwargs)

        return execute
    return decorator


class Populator:
    def __init__(self, client, opts):
        self.client = client
        self.opts = opts

    def load(self, obj, attributes_dict):
        with pretty_logger():
            self.handle_attributes(obj, attributes_dict)
            self.handle_relations(obj, attributes_dict)

    def handle_attributes(self, obj, raw):
        for field, field_type in obj._attrs.items():
            if field in raw:
                log(obj, field, raw[field])
                setattr(obj, field, raw[field])

    def handle_relations(self, obj, raw):
        relation_type_handlers = {
            'ONETOMANY': self.handle_o2m,
            'MANYTOONE': self.handle_m2o,
            'ONETOONE': self.handle_o2o,
        }
        for field in obj._relations.keys():
            val = raw.get(field, State.VOID)
            rel = rel_info(self.client, obj._relations, field)
            relation_type_handlers[rel.type](obj, field, val, rel.model)

    @log_loading('blue')
    def handle_o2m(self, obj, field, val, rel_model):
        typed_list = self.opts.TypedListClass(rel_model, obj, field)
        if val is not State.VOID:
            for rel_obj in val:
                if isinstance(rel_obj, dict):
                    rel_obj = rel_model(**rel_obj)
                with pretty_logger():
                    typed_list.append(rel_obj)
            setattr(obj, field, typed_list)

    @log_loading('cyan')
    def handle_m2o(self, obj, field, val, rel_model, color='cyan'):
        if isinstance(val, dict):
            val = rel_model(**val)
        if hasattr(val.__class__, '__bases__'):
            if 'BaseObject' in [k.__name__ for k in val.__class__.__bases__]:
                setattr(obj, field, val)

    @log_loading('magenta')
    def handle_o2o(self, obj, field, val, rel_model):
        self.handle_m2o(obj, field, val, rel_model, color='magenta')


class BaseObject:
    def __init__(self, **kwargs):
        super().__setattr__('id', kwargs.pop('id', generate_id()))
        self._populator.load(self, kwargs)
        self._client._register(self)

    def __new__(cls, **kwargs):
        key = None
        if kwargs.get('id'):
            key = '%s%s' % (cls.__name__, kwargs['id'])
        if key in cls._client.registry:
            obj = cls._client.registry[key]
            logger.debug(crayons.yellow('Using existing {}'.format(key)))
        else:
            obj = object.__new__(cls)
            obj._dirty = set()
            obj._values = {}
            logger.debug(crayons.yellow('initialising {}'.format(key)))
        return obj

    def __setattr__(self, name, value):
        if not name.startswith('_'):
            if name not in chain(self._relations, self._attrs):
                raise AttributeError('{} has no attribute named {}'.format(
                    self._class_name, name))
        if name in self._relations.keys():
            rel = rel_info(self._client, self._relations, name)
            if value and rel.type in ('MANYTOONE', 'ONETOONE'):
                allowed = (rel.model, LoadableProperty)
                if value.__class__ not in allowed:
                    msg = '%s must be an instance of %s, not %s'
                    raise Exception(msg % (name, rel.model_name,
                                           value.__class__.__name__))
        object.__setattr__(self, name, value)

    @classmethod
    def all(cls):
        # shorthand for Class.query.all()
        return cls.query.all()

    @classmethod
    def get(cls, oid):
        # shorthand for Class.query.get()
        registry_id = '{}{}'.format(cls.__name__, oid)
        if registry_id in cls._client.registry:
            return cls._client.registry[registry_id]
        return cls.query.get(oid)

    @classmethod
    def attributes(cls):
        return cls._attrs.keys()

    @classmethod
    def relations(cls):
        return cls._relations.keys()

    @classmethod
    def methods(cls):
        return cls._methods

    @property
    def is_new(self):
        return str(self._pkval).startswith('C')

    @property
    def _pkval(self):
        return getattr(self, self._pk_name)

    def _flat_dict(self):
        # create attribute dict
        object_dict = {}

        def clean(value):
            if isinstance(value, BaseObject):
                if value.is_new:
                    value.save()
                return {'id': value._pkval}
            return value

        for attr in self._dirty:
            value = getattr(self, attr)
            if isinstance(value, (list, set, tuple)):
                object_dict[attr] = [clean(v) for v in value]
            else:
                value = clean(value)
                if 'id' in value:
                    object_dict['{}_id'.format(attr['id'])]
                else:
                    object_dict[attr] = value['value']
        return object_dict

    def delete(self):
        if not self.is_new:
            url = '%s/%s' % (self._base_url, self._pkval)
            r = self._client.session.delete(url)
            if not r.status_code == 204:
                msg = "Unable to delete object %s, recieved status code %s: %s"
                raise Exception(msg % (self.__class__.__name__, r.status_code,
                                       r.content))
        return True

    def save(self):
        if self.is_new_object():
            self._connection.create(self)
        elif self._dirty:
            self._connection.update(self)
        else:
            logger.debug("No action needed")
        self._state = State.LOADABLE
        self._dirty = set()

    def __repr__(self):
        return str(self)

    def __str__(self):
        attributes = ["%s: %s".format(self._pk_name, self._pkval)]
        if hasattr(self, 'name'):
            attributes.append("name: %s" % self.name)
        return "<%s [%s]>" % (self.__class__.__name__, " | ".join(attributes))
