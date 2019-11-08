import logging
from itertools import chain

import crayons

from .utils import generate_id

logger = logging.getLogger('restless-client')


def get_class(cls, kwargs):
    if not cls._polymorphic.get('identities'):
        return cls
    discriminator_name = cls._polymorphic['on']
    for discriminator, kls in cls._polymorphic['identities'].items():
        if kwargs.get(discriminator_name) == discriminator:
            return cls._client._classes[kls]


class BaseObject:
    def __init__(self, **kwargs):
        oid = self._pk_name
        super().__setattr__(oid,
                            kwargs[oid] if oid in kwargs else generate_id())
        self._deserializer.load(self, kwargs)
        self._client._register(self)

    def __new__(cls, **kwargs):
        key = None
        if kwargs.get(cls._pk_name):
            key = '%s%s' % (cls.__name__, kwargs[cls._pk_name])
        if key in cls._client.registry:
            obj = cls._client.registry[key]
            logger.debug(crayons.yellow('Using existing {}'.format(key)))
        else:
            cls = get_class(cls, kwargs)
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
        self._relhelper.is_valid_instance(name, value)
        object.__setattr__(self, name, value)

    @classmethod  # noqa A003
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
        return list(cls._attrs.keys())

    @classmethod
    def relations(cls):
        return list(cls._relations.keys())

    @classmethod
    def methods(cls):
        return list(cls._methods)

    @property
    def is_new(self):
        return str(self._pkval).startswith('C')

    @property
    def _pkval(self):
        return getattr(self, self._pk_name)

    def delete(self):
        self._connection.delete(self)

    def save(self):
        if self.is_new:
            self._connection.create(self)
        elif self._dirty:
            self._connection.update(self)
        else:
            logger.debug("No action needed")
        self._dirty = set()

    def __repr__(self):
        return str(self)

    def __str__(self):
        attributes = ["{}: {}".format(self._pk_name, self._pkval)]
        if hasattr(self, 'name'):
            attributes.append("name: {}".format(self.name))
        return "<{} [{}]>".format(self.__class__.__name__,
                                  " | ".join(attributes))
