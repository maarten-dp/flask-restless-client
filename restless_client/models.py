import logging
from itertools import chain

import crayons

from .inspect import inspect
from .utils import generate_id

logger = logging.getLogger('restless-client')


def get_class(cls, kwargs, meta):
    if not meta.polymorphic.get('identities'):
        return cls
    discriminator_name = meta.polymorphic['on']
    for discriminator, kls in meta.polymorphic['identities'].items():
        if kwargs.get(discriminator_name) == discriminator:
            return meta.client._classes[kls]
    return cls


class BaseObject:
    def __init__(self, **kwargs):
        oid = self._rlc.pk_name
        super().__setattr__(oid,
                            kwargs[oid] if oid in kwargs else generate_id())
        self._rlc.deserializer.load(self, kwargs)
        self._rlc.client._register(self)

    def __new__(cls, **kwargs):
        key = None
        meta = cls._rlc
        if kwargs.get(meta.pk_name):
            key = '%s%s' % (cls.__name__, kwargs[meta.pk_name])
        if key in meta.client.registry:
            obj = meta.client.registry[key]
            logger.debug(crayons.yellow('Using existing {}'.format(key)))
        else:
            cls = get_class(cls, kwargs, meta)
            obj = object.__new__(cls)
            obj._rlc = inspect(obj)
            logger.debug(crayons.yellow('initialising {}'.format(key)))
        return obj

    def __setattr__(self, name, value):
        if not name.startswith('_'):
            if name not in chain(self._rlc._relations, self._rlc._attributes):
                raise AttributeError('{} has no attribute named {}'.format(
                    self._rlc.class_name, name))
        self._rlc.relhelper.is_valid_instance(name, value)
        object.__setattr__(self, name, value)

    def __repr__(self):
        return str(self)

    def __str__(self):
        attributes = ["{}: {}".format(self._rlc.pk_name, self._rlc.pk_val)]
        if hasattr(self, 'name'):
            attributes.append("name: {}".format(self.name))
        return "<{} [{}]>".format(self.__class__.__name__,
                                  " | ".join(attributes))
