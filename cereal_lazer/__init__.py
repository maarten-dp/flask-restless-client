"""
Small layer on top of serializer that:
- includes some additional objects already registered
- makes the serializing http friendly
- doing a name based registering on non-builtins

To better fit the needs.
"""
import serialize
from datetime import date, datetime
import pytz


NAME_BY_CLASS = {}


def encode_helper(obj, to_builtin):
    return dict(__class_name__= NAME_BY_CLASS[obj.__class__],
                __dumped_obj__=to_builtin(obj))


serialize.all.encode_helper = encode_helper


def register_class(name, klass, to_builtin, from_builtin):
    helper = serialize.all.ClassHelper(to_builtin, from_builtin)
    serialize.all.CLASSES_BY_NAME[name] = helper
    NAME_BY_CLASS[klass] = name
    serialize.register_class(klass, to_builtin, from_builtin)


def dumps(body, fmt):
    res = serialize.dumps(body, fmt)
    if fmt == 'msgpack':
        res = res.hex()
    return res


def loads(body, fmt):
    if fmt == 'msgpack':
        body = bytes.fromhex(body)
    return serialize.loads(body, fmt)


register_class(
    datetime.__name__,
    datetime,
    lambda x: (x.timetuple()[:-3], str(x.tzinfo) if x.tzinfo else None),
    lambda x: datetime(*x[0], tzinfo=pytz.timezone(x[1]) if x[1] else x[1]))
register_class(date.__name__, date, lambda x: x.timetuple()[:3], lambda x: date(*x))
