import logging

logger = logging.getLogger('bluesnake-client')

INVERT_OPERATORS = [
    ('==', '!='), ('>', '<='), ('<', '>='), ('>=', '<'),
    ('<=', '>'), ('in', 'not_in'), ('is_null', 'is_not_null')
]
INVERT_MAPPING = {}
for a, b in INVERT_OPERATORS:
    INVERT_MAPPING[a] = b
    INVERT_MAPPING[b] = a


def is_filter_result(f, operator):
    assert isinstance(f, (BooleanResult, ComparisonResult)), 'Wrong use of {}'.format(operator)


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
            raise Exception('{} is not a valid invert candidate'.format(self.op))
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
        if hasattr(val, '__bases__'):
            for klass in val.__bases__:
                if klass.__name__ == 'BaseObject':
                    val = val.id
        return val


class Query:
    def __init__(self, client, cls):
        self.client = client
        self.cls = cls
        self._query = {}

    def filter(self, *queries):
        q = []
        for query in queries:
            is_filter_result(query, 'filter')
            q.append(query.to_raw_filter())
        if not self._query.get('filters'):
            self._query['filters'] = []
        self._query['filters'].extend(q)
        return self

    def filter_by(self, **kwargs):
        filters = []
        for attr, value in kwargs.items():
            filters.append((getattr(self.cls, attr) == value).to_raw_filter())
        self._query['filters'] = filters
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

    def one(self):
        self._query['single'] = True
        return self.client.object_loader.load_objs(self.cls, q=self._query)

    def one_or_none(self):
        try:
            return self.one()
        except Exception as e:
            if 'Bad Request' in str(e):
                raise e
            return None

    def all(self):
        kwargs = {}
        if self._query:
            kwargs['q'] = self._query
        return self.client.object_loader.load_objs(self.cls, **kwargs)

    def get(self, oid):
        return self.client.object_loader.load_obj(self.cls, oid)

    # def resolve_relations_queries(self):
    #     # restless doesn't seem to handle complex relations very well, so
    #     # we're doing it the hard way and loading every step of the relation
    #     filters = []
    #     for query in self._relational_queries:
    #         res = self._resolve_initial(query.name.pop(0), query.op, query.val)
    #         for name in query.name:
    #             res = self._resolve(name, res)
    #         filters.append(name.parent.id.in_([r.id for r in res]).to_raw_filter())
    #     return filters

    # def _resolve_initial(self, history, op, val):
    #     raw = ComparisonResult(history.parent_attribute, op, val).to_raw_filter()
    #     return self.client.object_loader.load_objs(history.parent, q={'filters': [raw]})

    # def _resolve(self, history, res):
    #     ids = [r.id for r in res]
    #     return [o for o in history.klass.all() if o.id in ids]
