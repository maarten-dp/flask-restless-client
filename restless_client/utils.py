import logging
import re
from contextlib import contextmanager
from enum import Enum

from dateutil import parser
from pytz import UTC

LIKELY_PARSABLE_DATETIME = r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})|(\d{8}T\d{6}Z?)"
logger = logging.getLogger('restless-client')

LOCAL_ID_COUNT = 0
DEPTH = 0


class State(Enum):
    VOID = 1
    LOADING = 2
    LOADABLE = 3


def generate_id():
    global LOCAL_ID_COUNT
    LOCAL_ID_COUNT += 1
    return 'C{}'.format(LOCAL_ID_COUNT)


def urljoin(*args):
    return "/".join(args)


def datetime_from_value(value, as_timezone):
    if isinstance(value, str) and re.search(LIKELY_PARSABLE_DATETIME, value):
        return parser.parse(value).astimezone(as_timezone)
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            if isinstance(item, dict):
                value[idx] = parse_custom_types(item)
            else:
                value[idx] = datetime_from_value(item, as_timezone)

    return value


def parse_custom_types(dct, as_timezone=UTC, **kwargs):
    for k, v in dct.items():
        try:
            if isinstance(v, dict):
                dct[k] = parse_custom_types(v, as_timezone)
            else:
                dct[k] = datetime_from_value(v, as_timezone)
        except Exception:
            pass

    return dct


class UserException(Exception):
    pass


class LoadingManager:
    def __init__(self, client):
        self.client = client
        self.active_contexts = 0

    def __enter__(self):
        self.active_contexts += 1
        self.client.state = State.LOADING

    def __exit__(self, exc_type, exc_value, traceback):
        self.active_contexts -= 1
        if self.active_contexts == 0:
            self.client.state = State.LOADABLE


class RelationHelper:
    def __init__(self, client, opts, relations):
        self.client = client
        self.opts = opts
        self.relations = relations

    def type(self, name):  # noqa A003
        return self.relations[name]['relation_type']

    def model_name(self, name):
        return self.relations[name]['foreign_model']

    def model(self, name):
        return self.client._classes[self.model_name(name)]

    def column_name(self, name):
        if name not in self.relations:
            return name
        return self.relations[name].get('local_column', name)

    def backref(self, name):
        return self.relations[name].get('backref')

    def is_scalar(self, name):
        return self.type(name) in ('MANYTOONE', 'ONETOONE')

    def is_valid_instance(self, name, instance):
        if name in self.relations.keys() and self.is_scalar(name):
            allowed = (self.model(name), self.opts.LoadableProperty,
                       type(None))
            if not isinstance(instance, allowed):
                msg = '{} must be an instance of {}, not {}'
                raise Exception(
                    msg.format(name, self.model_name(name),
                               instance.__class__.__name__))


@contextmanager
def pretty_logger(depth=2):
    global DEPTH
    DEPTH += depth
    yield
    DEPTH -= depth


def get_depth():
    return DEPTH
