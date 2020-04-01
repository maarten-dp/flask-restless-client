import logging

from prettytable import PrettyTable

logger = logging.getLogger('restless-client')


def update_backref(remove):
    def outer_decorator(fn):
        def decorator(self, *args, **kwargs):
            res = fn(self, *args, **kwargs)
            item = res or args[0]
            if not self.parent._rlc.client.is_loading:
                self.parent._rlc.dirty.add(self.for_attr)
            if self.for_attr:
                self._update_backref(item, self.for_attr, remove=remove)
            return res

        return decorator

    return outer_decorator


class TypedList(list):
    def __init__(self, otype, parent, for_attr=None):
        self.type = otype
        self.parent = parent
        self.for_attr = for_attr

    @update_backref(remove=False)
    def append(self, item):
        if not isinstance(item, self.type):
            cls_name = item.__class__.__name__
            msg = 'Only {} can be added, {} provided'
            raise TypeError(msg.format(self.type.__name__, cls_name))
        list.append(self, item)

    def extend(self, lst):
        for i in lst:
            self.append(i)

    @update_backref(remove=True)
    def remove(self, item):
        list.remove(self, item)

    @update_backref(remove=True)
    def pop(self):
        return list.pop(self)

    def _update_backref(self, item, attr, remove=False):
        relhelper = self.parent._rlc.relhelper
        backref = relhelper.backref(attr)
        if backref:
            msg = 'Updating {} backref {}.{}'.format(
                item._rlc.relhelper.type(backref), item, backref)
            if item._rlc.relhelper.is_scalar(backref):
                value = None if remove else self.parent
                logger.debug(msg)
                with self.parent._rlc.client.loading:
                    setattr(item, backref, value)
            else:
                if backref in item._rlc.values:
                    fn = list.remove if remove else list.append
                    lst = getattr(item, backref)
                    if (self.parent not in lst) ^ remove:
                        logger.debug(msg)
                        fn(lst, self.parent)


# only used for printing puroposes, has no functional benefit
class ObjectCollection(list):
    def __init__(self, object_class, lst=None, attrs=None):
        self.object_class = object_class
        self.attrs = attrs or object_class._rlc.attributes()
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
            if len(val) > 25:
                val = '{}...'.format(val[:22])
            return val

        for obj in self:
            values = obj._values
            pt.add_row(
                [truncate(str(values.get(header))) for header in headers])
        res = pt.get_string(border=False, sortby="id")
        if not res:
            pt.add_row(['' for header in headers])
            res = pt.get_string(border=False, sortby="id")
        return res

    def __repr__(self):
        return self.pprint()
