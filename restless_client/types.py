import json
from collections import defaultdict

from dateutil import parser

CASTERS = {}
OBJECT_HOOKS = defaultdict(dict)


def register_type(type_name, caster):
    CASTERS[type_name] = caster


def cast_type(value, desired_type, raise_on_error=False):
    if desired_type in CASTERS:
        try:
            return CASTERS[desired_type](value)
        except Exception as e:
            if raise_on_error:
                raise e
    return value


def date_caster(value):
    return parser.parse(value).date()


def datetime_caster(value):
    return parser.parse(value)


def boolean_caster(value):
    if value in ('False', 'false', '0', 'no'):
        return False
    bool(value)


def json_caster(value):
    return json.loads(value)


register_type('date', date_caster)
register_type('datetime', datetime_caster)
register_type('utcdatetime', datetime_caster)
register_type('boolean', boolean_caster)
register_type('json', json_caster)
register_type('jsontype', json_caster)


def object_hook(attr):
    def outer_decorator(fn):
        model = attr.parent_klass
        attribute = attr.parent_attribute
        OBJECT_HOOKS[model][attribute] = fn
        return fn

    return outer_decorator


def object_hook_emit(model, attribute, value):
    if model in OBJECT_HOOKS:
        fn = OBJECT_HOOKS[model].get(attribute)
        if fn:
            return fn(value)
    return value
