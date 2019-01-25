from bluesnake_client.filter import Query
from bluesnake_client.connection import LoadableProperty
from bluesnake_client.utils import (urljoin, generate_id, classproperty, State,
    pretty_logger)
import logging

logger = logging.getLogger('bluesnake-client')


def create_method_function(client, name, details):
    method_url = details['url']

    def fn(self, **kwargs):
        additional = ""
        for arg in details['args']:
            additional += "/%s" % kwargs[arg]
        if isinstance(self.id, str) and self.id.startswith('C'):
            raise Exception('Cannot use methods on newly created objects')
        url_params = {
            'target': self.__class__.__name__.lower(),
            'oid': self.id,
            'method': name,
            'additional': additional
        }
        suffix = method_url.format(**url_params)
        if suffix.startswith("/"):
            suffix = suffix[1:]
        url = urljoin(client.model_url, suffix)
        return client.object_loader.load_raw(
            url, as_timezone=client._timezone, **kwargs)

    return fn


class BaseObject:
    def __init__(self, **kwargs):
        super().__setattr__('id', kwargs.pop('id', generate_id()))
        with pretty_logger():
            self._parent.object_loader.load_obj_from_dict(self, kwargs)
        self._parent._register(self)

    def __new__(cls, **kwargs):
        key = None
        if kwargs.get('id'):
            key = '%s%s' % (cls.__name__, kwargs['id'])
        if key in cls._parent.registry:
            obj = cls._parent.registry[key]
            logger.debug('Using existing {}'.format(key))
        else:
            obj = object.__new__(cls)
            obj._dirty = []
            obj._values = {}
            logger.debug('initialising {}'.format(key))
        return obj

    def __setattr__(self, name, value):
        if name in self._relations.keys():
            rel_type = self._relations[name]['relation_type']
            rel_model = self._relations[name]['foreign_model']
            if value and rel_type == 'o2m':
                allowed = (self._parent._classes[rel_model], LoadableProperty)
                if value.__class__ not in allowed:
                    msg = '%s must be an instance of %s, not %s'
                    raise Exception(msg % (name, rel_model,
                                           value.__class__.__name__))
        object.__setattr__(self, name, value)

    @classproperty
    def query(cls):
        return Query(cls._parent, cls)

    @classmethod
    def all(cls):
        # shorthand for Class.query.all()
        return Query(cls._parent, cls).all()

    @classmethod
    def get(cls, oid):
        # shorthand for Class.query.get()
        registry_id = '{}{}'.format(cls.__name__, oid)
        if registry_id in cls._parent.registry:
            return cls._parent.registry[registry_id]
        return Query(cls._parent, cls).get(oid)

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
        return str(self.id).startswith('C')

    def _flat_dict(self):
        # create attribute dict
        object_dict = {}

        def clean(value):
            if isinstance(value, BaseObject):
                if value.is_new:
                    value.save()
                return {'id': value.id}
            return {'value': value}

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
            url = '%s/%s' % (self._base_url, self.id)
            r = self._parent.session.delete(url)
            if not r.status_code == 204:
                msg = "Unable to delete object %s, recieved status code %s: %s"
                raise Exception(msg % (self.__class__.__name__, r.status_code,
                                       r.content))
        return True

    def save(self):
        if self.is_new_object():
            self._create()
        elif self._dirty:
            self._update()
        else:
            logger.debug("No action needed")
        self._state = State.LOADABLE
        self._dirty = []

    def _create(self):
        object_dict = self._flat_dict()
        logger.debug("Creating: %s" % self._base_url)
        logger.debug("Body: %s" % object_dict)
        r = self._parent.session.post(self._base_url, json=object_dict)
        if r.ok:
            self.id = r.json()['id']
        else:
            msg = "Unable to create object %s, recieved status code %s: %s"
            raise Exception(msg % (self.__class__.__name__, r.status_code,
                                   r.content))

    def _update(self):
        object_dict = self._flat_dict()
        url = urljoin(self._base_url, str(self.id))
        logger.debug("Updating: %s" % url)
        logger.debug("Body: %s" % object_dict)
        r = self._parent.session.put(url, json=object_dict)
        if not r.ok:
            msg = "Unable to update object %s, recieved status code %s: %s"
            raise Exception(msg % (self.__class__.__name__, r.status_code,
                                   r.content))

    def __repr__(self):
        return str(self)

    def __str__(self):
        attributes = ["id: %s" % self.id]
        if hasattr(self, 'name'):
            attributes.append("name: %s" % self.name)
        return "<%s [%s]>" % (self.__class__.__name__, " | ".join(attributes))
