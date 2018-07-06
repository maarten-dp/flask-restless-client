from webargs import fields
import re
import json
from dateutil.parser import parse as dtparse
from functools import partial
from cereal_lazer.parser import get_parser


def serialize(value):
    return DynamicType()._serialize(value, None, None)


def deserialize(value):
    return DynamicType()._deserialize(value, None, None)


def parse_type(value):
    # looking for type B:
    # the parser fails if type A comes before type B where A is a substring of B
    # i.e.: date, datetime
    types = sorted(TYPES.keys(), key=lambda x: len(x), reverse=True)
    try:
        return get_parser(types).parseString(value)
    except Exception:
        return None, value


def parser_for(model):
    def parse_object(value):
        return model.query.get(value)
    return parse_object


def register_parsable_type(tp, parser):
    global TYPES
    TYPES[tp] = parser


def _deserialize(tp, value):
    return TYPES[tp]().deserialize(value, None, None)


class DynamicType(fields.String):
    def _deserialize(self, value, attr, data):
        tp, value = parse_type(value)
        if not tp:
            return value
        return _deserialize(tp, value)

    def _serialize(self, value, attr, obj):
        type_str = type(value).__name__
        value =  TYPES.get(type_str, fields.String)()._serialize(value, attr, obj)
        if type_str not in TYPES:
            type_str = 'str'
        return '<{}|{}|>'.format(type_str, value)


class Dict(fields.Dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.container = DynamicType()

    def _deserialize(self, value, attr, data):
        c = partial(self.container._deserialize, data=data, attr=attr)
        return {_deserialize(*k): _deserialize(*v) for k,v in value}

    def _serialize(self, value, attr, obj):
        c = partial(self.container._serialize, obj=obj, attr=attr)
        return ','.join(['{}:{}'.format(c(k), c(v)) for k, v in value.items()])


class List(fields.String):
    type_cls = list
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.container = DynamicType()

    def _deserialize(self, value, attr, data):
        c = partial(self.container._deserialize, data=data, attr=attr)
        return self.type_cls([_deserialize(*v) for v in value])

    def _serialize(self, value, attr, obj):
        c = partial(self.container._serialize, obj=obj, attr=attr)
        return ','.join([c(v) for v in value])


class Set(List):
    type_cls = set


class Tuple(List):
    type_cls = tuple


TYPES = {
    'int': fields.Integer,
    'float': fields.Number,
    'str': fields.String,
    'list': List,
    'set': Set,
    'tuple': Tuple,
    'dict': Dict,
    'bool': fields.Boolean,
    'date': fields.Date,
    'datetime': fields.DateTime,
    'time': fields.Time,
}
