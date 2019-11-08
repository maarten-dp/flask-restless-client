import logging
from datetime import date, datetime
from itertools import chain

import crayons

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


class ObjectSerializer:
    def __init__(self, client, opts):
        self.client = client
        self.opts = opts

    def serialize(self, obj):
        to_serialize = list(chain(obj.attributes(), obj.relations()))
        return self._serialize(obj, to_serialize)

    def serialize_dirty(self, obj):
        return self._serialize(obj, obj._dirty, autosave=True)

    def _serialize(self, obj, to_serialize, autosave=False):
        # create attribute dict
        if obj._pk_name in to_serialize:
            to_serialize.remove(obj._pk_name)
        object_dict = {}
        for attr in to_serialize:
            value = obj._values[attr]
            object_dict[attr] = self.clean(attr, value, autosave)
        return object_dict

    def clean(self, attr, value, autosave):
        if isinstance(value, self.opts.BaseObject):
            if value.is_new and autosave:
                value.save()
            value = {value._pk_name: value._pkval}
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
            handler = relation_type_handlers[obj._relhelper.type(field)]
            handler(obj, field, val, obj._relhelper.model(field))

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
        elif obj.is_new:
            setattr(obj, field, typed_list)

    @log_loading('cyan')
    def handle_m2o(self, obj, field, val, rel_model):
        if isinstance(val, dict):
            val = rel_model(**val)
        if hasattr(val.__class__, '__bases__'):
            if self.opts.BaseObject in val.__class__.__bases__:
                setattr(obj, field, val)

    @log_loading('magenta')
    def handle_o2o(self, obj, field, val, rel_model):
        self.handle_m2o(obj, field, val, rel_model)
