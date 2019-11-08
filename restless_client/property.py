import logging

from restless_client.filter import ComparisonResult, FilterMixIn
from restless_client.utils import State

logger = logging.getLogger('restless-client')
NOT_UPDATING_MSG = "Not updating {}.{} (dirty and in load state)"


class LoadableProperty:
    def __init__(self, attribute):
        self.attribute = attribute

    def __set__(self, obj, value):
        dirty = self.attribute in obj._dirty
        if dirty and obj._client.is_loading:
            logger.debug(NOT_UPDATING_MSG.format(obj, self.attribute))
            return
        obj._values[self.attribute] = value
        if not obj._client.is_loading:
            obj._dirty.add(self.attribute)

    def __get__(self, obj, objtype=None):
        if objtype and obj is None:
            # if obj is None, the __get__ is invoked on class level
            # returning FilterNode will allow the user to build filters
            return FilterNode(objtype, self.attribute)
        if self.getval(obj) is State.VOID and not obj.is_new:
            args = (obj.__class__, obj._pkval)
            logger.debug('Loading {} with id {} remotely'.format(*args))
            obj._connection.load(*args)
        if self.getval(obj) is State.VOID:
            return None
        return self.getval(obj)

    def getval(self, obj):
        return obj._values.get(self.attribute, State.VOID)


class FilterNode(FilterMixIn):
    def __init__(self, parent, parent_attribute, parent_node=None):
        self.parent_klass = parent
        self.parent_attribute = parent_attribute
        self.parent_node = parent_node
        self.klass = None
        self.rel_type = None
        self.is_leaf = True
        if parent_attribute in parent._relations:
            self.rel_type = parent._relations[parent_attribute][
                'relation_type']
            class_name = parent._relations[parent_attribute]['foreign_model']
            self.klass = parent._client._classes[class_name]

    def __getattr__(self, attr):
        if attr not in self.klass.attributes(
        ) and attr not in self.klass.relations():
            msg = '{} has no attribute named {}'
            raise AttributeError(msg.format(self.klass._class_name, attr))
        return FilterNode(self.klass, attr, parent_node=self)

    def _assemble_filter(self, op, val):
        attribute, val = self._transform_relation(self.parent_attribute, val)

        rfilter = ComparisonResult(attribute, op, self._clean(val))
        if not self.is_leaf:
            return rfilter

        rp = self
        while rp.parent_node:
            rp.parent_node.is_leaf = False
            if rp.parent_node.rel_type == 'ONETOMANY':
                rfilter = rp.parent_node.any_(rfilter)
            else:
                rfilter = rp.parent_node.has_(rfilter)
            rp = rp.parent_node
        return rfilter

    def _transform_relation(self, attribute, val):
        if hasattr(val, '__class__') and hasattr(val.__class__, '__bases__'):
            for klass in val.__class__.__bases__:
                if klass.__name__ == 'BaseObject':
                    val = val._pkval
                    rel_def = self.parent_klass._relations[
                        self.parent_attribute]
                    attribute = rel_def['local_column']
        return attribute, val
