import logging
from datetime import date, datetime
from itertools import chain

import crayons

from .types import cast_type, object_hook_emit
from .utils import State, pretty_logger

logger = logging.getLogger('restless-client')
LOAD_MSG = 'loading {}.{} with value {}'


def log(o, a, v, attr_color='red'):
    logger.info(
        LOAD_MSG.format(
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


def set_attr(obj, attr, value):
    if value and value is not State.VOID:
        value = object_hook_emit(obj.__class__, attr, value)
    setattr(obj, attr, value)


class ObjectSerializer:
    def __init__(self, client, opts):
        self.client = client
        self.opts = opts

    def serialize(self, obj):
        to_serialize = list(chain(obj._rlc.attributes(), obj._rlc.relations()))
        return self._serialize(obj, to_serialize)

    def serialize_dirty(self, obj):
        return self._serialize(obj, obj._rlc.dirty, autosave=True)

    def _serialize(self, obj, to_serialize, autosave=False):
        # create attribute dict
        if obj._rlc.pk_name in to_serialize:
            to_serialize.remove(obj._rlc.pk_name)
        return self._raw_serialize(obj, to_serialize, autosave)

    def _raw_serialize(self, obj, to_serialize, autosave=False):
        object_dict = {}
        for attr in to_serialize:
            if attr not in obj._rlc.values:
                continue
            value = obj._rlc.values[attr]
            object_dict[attr] = self.clean(attr, value, autosave)
        return object_dict

    def clean(self, attr, value, autosave):
        if isinstance(value, self.opts.BaseObject):
            if value._rlc.is_new and autosave:
                value._rlc.save()
            value = {value._rlc.pk_name: value._rlc.pk_val}
        if isinstance(value, (date, datetime)):
            value = value.isoformat()
        if isinstance(value, (list, set, tuple)):
            value = [self.clean(attr, v, autosave) for v in value]
        return value


class ObjectDeserializer:
    def __init__(self, client, opts):
        self.client = client
        self.opts = opts

    def load(self, obj, attributes_dict):
        with pretty_logger():
            self.handle_attributes(obj, attributes_dict)
            self.handle_relations(obj, attributes_dict)

    def handle_attributes(self, obj, raw):
        attrs = obj._rlc._attributes
        for field, field_type in attrs.items():
            if field in raw:
                log(obj, field, raw[field])
                value_type = attrs.get(field)
                value = cast_type(raw[field], value_type)
                set_attr(obj, field, value)

    def handle_relations(self, obj, raw):
        relation_type_handlers = {
            'ONETOMANY': self.handle_o2m,
            'MANYTOONE': self.handle_m2o,
            'ONETOONE': self.handle_o2o,
            'MANYTOMANY': self.handle_o2m,
        }
        for field in obj._rlc._relations.keys():
            val = raw.get(field, State.VOID)
            handler = relation_type_handlers[obj._rlc.relhelper.type(field)]
            handler(obj, field, val, obj._rlc.relhelper.model(field))

    @log_loading('blue')
    def handle_o2m(self, obj, field, val, rel_model):
        typed_list = self.opts.TypedListClass(rel_model, obj, field)
        if val is not State.VOID:
            for rel_obj in val:
                if isinstance(rel_obj, dict):
                    rel_obj = rel_model(**rel_obj)
                with pretty_logger():
                    typed_list.append(rel_obj)
            set_attr(obj, field, typed_list)
        elif obj._rlc.is_new:
            set_attr(obj, field, typed_list)

    @log_loading('cyan')
    def handle_m2o(self, obj, field, val, rel_model):
        if isinstance(val, dict):
            val = rel_model(**val)
        if hasattr(val.__class__, '__bases__'):
            if self.opts.BaseObject in val.__class__.__bases__:
                set_attr(obj, field, val)

    @log_loading('magenta')
    def handle_o2o(self, obj, field, val, rel_model):
        self.handle_m2o(obj, field, val, rel_model)
