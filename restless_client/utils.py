import re
from dateutil import parser
from prettytable import PrettyTable
from pytz import UTC
import logging
from enum import Enum
from contextlib import contextmanager
from collections import namedtuple

LIKELY_PARSABLE_DATETIME = r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})|(\d{8}T\d{6}Z?)"
logger = logging.getLogger('restless-client')

LOCAL_ID_COUNT = 0
DEPTH = 0


class State(Enum):
    VOID = 1
    UNLOADED = 2
    LOADED = 3
    LOADING = 4
    LOADABLE = 5
    NOT_LOADABLE = 6
    DIRTY = 7
    NEW = 8


RelationInfo = namedtuple('RelationInfo', 'type model_name model')


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


class classproperty(object):
    def __init__(self, fget):
        self.fget = fget

    def __get__(self, owner_self, owner_cls):
        return self.fget(owner_cls)


class UserException(Exception):
    pass


class TypedList(list):
    def __init__(self, otype, parent, for_attr=None):
        self.type = otype
        self.parent = parent
        self.for_attr = for_attr

    def append(self, item):
        if self.parent._client.state != State.LOADING:
            self.parent._dirty.append(self.for_attr)
        cls_name = item.__class__.__name__
        if not isinstance(item, self.type):
            msg = 'Only {} can be added, {} provided'
            raise TypeError(msg.format(self.type.__name__, cls_name))
        if item in self:
            msg = 'Object {} with id {} is already in this list'
            raise UserException(msg.format(self.type.__name__, item._pkval))
        super(TypedList, self).append(item)
        if self.for_attr:
            self._update_backref(item, self.for_attr)

    def _update_backref(self, item, attr, remove=False):
        rel_details = self.parent._relations[attr]
        backref = rel_details.get('backref')
        if backref:
            msg = 'Updating {} backref {}.{}'
            reltype = item._relations[backref]['relation_type']
            logger.debug(msg.format(reltype, item, rel_details['backref']))
            if reltype == 'o2m':
                value = self.parent
                if remove:
                    value = None
                setattr(item, rel_details['backref'], value)
            if reltype == 'm2o':
                if rel_details['backref'] in item._values:
                    lst = getattr(item, rel_details['backref'])
                    if remove:
                        if self.parent in lst:
                            list.remove(lst, self.parent)
                    else:
                        if self.parent not in lst:
                            list.append(lst, self.parent)
                    if self.parent._client.state != State.LOADING:
                        item._dirty.append(rel_details['backref'])

    def remove(self, item):
        super(TypedList, self).remove(item)
        if self.parent._client.state != State.LOADING:
            self.parent._dirty.append(self.for_attr)
        if self.for_attr:
            self._update_backref(item, self.for_attr, remove=True)


# only used for printing puroposes, has no functional benefit
class ObjectCollection(list):
    def __init__(self, object_class, lst=None, attrs=None):
        self.object_class = object_class
        self.attrs = attrs or object_class.attributes()
        if lst:
            self.extend(lst)

    def first(self):
        return self[0]

    def one(self):
        if len(self) > 1:
            raise ValueError('more than one result')
        return self.first()

    def __getitem__(self, key):
        if isinstance(key, int):
            return list.__getitem__(self, key)
        if isinstance(key, str):
            key = [key]
        return ObjectCollection(self.object_class, self, attrs=key)

    def pprint(self):
        attrs = self.attrs
        # make sure id and name are at the front of the table
        headers = ['id']
        if 'name' in attrs:
            headers.append('name')
        columns = set(attrs).difference(set(['id', 'name']))
        relation_columns = [c for c in columns if str(c).endswith('_id')]
        data_columns = columns.difference(set(relation_columns))
        # make sure to show the data columns next
        headers.extend(sorted(data_columns))
        # then show relation columns
        headers.extend(sorted(relation_columns))
        pt = PrettyTable(headers)
        pt.align = 'l'

        def truncate(val):
            val = val.replace('\n', '')
            if len(val) > 50:
                val = '{}...'.format(val[:47])
            return val

        for obj in self:
            pt.add_row([truncate(str(getattr(obj, header))) for header in headers])
        res = pt.get_string(border=False, sortby="id")
        if not res:
            pt.add_row(['' for header in headers])
            res = pt.get_string(border=False, sortby="id")
        return res

    def __repr__(self):
        return self.pprint()


@contextmanager
def pretty_logger(depth=2):
    global DEPTH
    DEPTH += depth
    yield
    DEPTH -= depth


def get_depth():
    return DEPTH


def rel_info(client, relations, name):
    rel_type = relations[name]['relation_type']
    rel_model_name = relations[name]['foreign_model']
    rel_model = client._classes[rel_model_name]
    return RelationInfo(rel_type, rel_model_name, rel_model)

