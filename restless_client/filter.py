import json
import logging

from .inspect import inspect

logger = logging.getLogger('restless-client')

INVERT_OPERATORS = [('==', '!='), ('>', '<='), ('<', '>='), ('>=', '<'),
                    ('<=', '>'), ('in', 'not_in'), ('is_null', 'is_not_null')]
INVERT_MAPPING = {}
for a, b in INVERT_OPERATORS:
    INVERT_MAPPING[a] = b
    INVERT_MAPPING[b] = a


def is_filter_result(f, operator):
    assert isinstance(
        f,
        (BooleanResult, ComparisonResult)), 'Wrong use of {}'.format(operator)


class FilterCollection(list):
    def to_raw_filter(self):
        return [i.to_raw_filter() for i in self]


class BooleanResult:
    def __init__(self, operator, collection):
        self.operator = operator
        assert isinstance(collection, FilterCollection)
        self.collection = collection

    def __and__(self, other):
        return self.__boolean_operator('and', other)

    def __or__(self, other):
        return self.__boolean_operator('or', other)

    def __boolean_operator(self, operator, other):
        is_filter_result(self, operator)
        is_filter_result(other, operator)
        if self.operator == operator:
            self.collection.append(other)
            return self
        return BooleanResult(operator, FilterCollection([self, other]))

    def to_raw_filter(self):
        return {self.operator: [c.to_raw_filter() for c in self.collection]}

    def __str__(self):
        return str(self.to_raw_filter())


class ComparisonResult:
    def __init__(self, name, op, val):
        self.name = name
        self.op = op
        self.val = val

    def __invert__(self):
        if self.op not in INVERT_MAPPING:
            raise Exception('{} is not a valid invert candidate'.format(
                self.op))
        return ComparisonResult(self.name, INVERT_MAPPING[self.op], self.val)

    def __and__(self, other):
        return self.__boolean_operator('and', other)

    def __or__(self, other):
        return self.__boolean_operator('or', other)

    def __boolean_operator(self, operator, other):
        is_filter_result(self, operator)
        is_filter_result(other, operator)
        if isinstance(other, BooleanResult) and other.operator == operator:
            other.collection.append(self)
            return other
        return BooleanResult(operator, FilterCollection([self, other]))

    def to_raw_filter(self):
        return {"name": self.name, "op": self.op, "val": self.val}

    def __str__(self):
        return str(self.to_raw_filter())


class FilterMixIn:
    def __eq__(self, other):
        return self._assemble_filter('==', other)

    def __ne__(self, other):
        return self._assemble_filter('!=', other)

    def __gt__(self, other):
        return self._assemble_filter('>', other)

    def __ge__(self, other):
        return self._assemble_filter('>=', other)

    def __lt__(self, other):
        return self._assemble_filter('<', other)

    def __le__(self, other):
        return self._assemble_filter('<=', other)

    def in_(self, items):
        return self._assemble_filter('in', items)

    def has_(self, comparison_result):
        assert isinstance(comparison_result, ComparisonResult)
        return self._assemble_filter('has', comparison_result.to_raw_filter())

    def any_(self, comparison_result):
        assert isinstance(comparison_result, ComparisonResult)
        return self._assemble_filter('any', comparison_result.to_raw_filter())

    def like_(self, other):
        return self._assemble_filter('like', other)

    def _assemble_filter(self, op, val):
        return ComparisonResult(self.attribute, op, self._clean(val))

    def _clean(self, val):
        return val


class QueryFactory:
    def __init__(self, connection, cls):
        self.connection = connection
        self.cls = cls

    def __get__(self, obj, objtype=None):
        if obj:
            raise AttributeError('Cannot call query on from an instance')
        return Query(self.connection, self.cls)

    def __set__(self, obj, value):
        raise ValueError('Cannot set query')


class Query:
    def __init__(self, connection, cls):
        self.connection = connection
        self.cls = cls
        self._query = {}

    def filter(self, *queries):  # noqa A003
        q = []
        for query in queries:
            is_filter_result(query, 'filter')
            q.append(query.to_raw_filter())
        if not self._query.get('filters'):
            self._query['filters'] = []
        self._query['filters'].extend(q)
        return self

    def filter_by(self, **kwargs):
        filters = []  # noqa F841
        for attr, value in kwargs.items():
            self.filter(getattr(self.cls, attr) == value)
        return self

    def limit(self, limit):
        assert int(limit)
        self._query['limit'] = limit
        return self

    def offset(self, offset):
        assert int(offset)
        self._query['offset'] = offset
        return self

    def order_by(self, **kwargs):
        order_by = []
        for attr, direction in kwargs.items():
            order_by.append({"field": attr, "direction": direction})
        if order_by:
            self._query['order_by'] = order_by
        return self

    def group_by(self, *group_by):
        if group_by:
            self._query['group_by'] = group_by
        return self

    def first(self):
        self.limit(1)
        self.order_by(**{self.cls._rlc.pk_name: 'asc'})
        return self.one()

    def last(self):
        self.limit(1)
        self.order_by(**{self.cls._rlc.pk_name: 'desc'})
        return self.one()

    def one(self):
        self._query['single'] = True
        kwargs = {'single': True}
        if self._query:
            kwargs['q'] = self._get_query()
        return self.connection.load_query(self.cls, **kwargs)

    def one_or_none(self):
        try:
            return self.one()
        except Exception as e:
            if 'Multiple results found' in str(e):
                raise e

    def all(self):  # noqa A003
        kwargs = {}
        if self._query:
            kwargs['q'] = self._get_query()
        return self.connection.load_query(self.cls, **kwargs)

    def get(self, oid):
        registry_id = '{}{}'.format(self.cls.__name__, oid)
        meta = inspect(self.cls)
        if registry_id in meta.client.registry:
            return meta.client.registry[registry_id]
        return self.connection.load(self.cls, oid)

    def _get_query(self):
        return json.dumps(self._query)
