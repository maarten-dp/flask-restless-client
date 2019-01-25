import requests
import pprint
import logging
from bluesnake_client.utils import (parse_custom_types, TypedList, urljoin,
    ObjectCollection, State, pretty_logger)
import crayons
from bluesnake_client.filter import FilterMixIn, ComparisonResult
from functools import partial
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger('bluesnake-client')
LOAD_MSG = 'loading {}.{} with value {}'


def log_load(o, a, v, attr_color='red'):
    logger.info(LOAD_MSG.format(
        crayons.black(o, always=True, bold=True),
        getattr(crayons, attr_color)(a, always=True, bold=True),
        crayons.green(str(v)[:150], always=True, bold=True)))


class AuthenticationError(Exception):
    pass


class AuthedSession(requests.Session):
    def __init__(self, url=None, username=None, password=None, token=None,
                 verify=True, trust_env=True, **kwargs):
        super().__init__(**kwargs)
        self.verify = verify
        self.trust_env = trust_env
        if url and username:
            self.authenticate(url, username, password)
        elif url and token:
            self.authenticate(url, token)

    def authenticate(self, url, username, password=None):
        payload = {
            'email': username,
            'password': password
        }
        r = self.post(url, data=payload)
        if not r.ok:
            raise AuthenticationError(r.content)
        try:
            token = r.json().get('access_token')
        except Exception as e:
            raise AuthenticationError("An error occured when authenticating".format(e))

        if not token:
            msg = ('An error occurred when authenticating: %s' % r.json())
            AuthenticationError(msg)
        self.headers.update({
            'Authorization': 'Bearer {}'.format(token)
        })

    def request(self, *args, **kwargs):
        return self.validate_response(super().request(*args, **kwargs))

    def validate_response(self, res):
        # raise an exception if status is 400 or up
        try:
            json_data = res.json()
        except Exception:
            json_data = {'message': 'Unspecified error ({})'.format(res.content)}
        # prepare error message
        res.reason = "{} ({})".format(res.reason, json_data)
        # raise if needed
        res.raise_for_status()
        return res


class ObjectLoader:
    def __init__(self, session):
        self.session = session

    def load_objs(self, obj_class, **kwargs):
        with obj_class._parent.loading:
            return self._load_objs(obj_class, **kwargs)

    def _load_objs(self, obj_class, **kwargs):
        raw = self.load_raw(obj_class._base_url, **kwargs)
        if 'q' in kwargs:
            if kwargs['q'].get('single', False):
                return obj_class(**raw)
        # iterate over pages
        objects = raw['objects']
        for page in range(2, raw['total_pages'] + 1):
            kwargs['page'] = page
            objects.extend(self.load_raw(obj_class._base_url, **kwargs)['objects'])
        return ObjectCollection(obj_class, set([obj_class(**obj) for obj in objects]))

    def load_obj(self, obj_class, obj_id):
        with obj_class._parent.loading:
            raw = self.load_raw(urljoin(obj_class._base_url, str(obj_id)))
            return obj_class(**raw)

    def load_obj_from_dict(self, obj, attributes_dict):
        raw = attributes_dict

        # Attributes
        for field, field_type in obj._attrs.items():
            if field in raw:
                log_load(obj, field, raw[field])
                setattr(obj, field, raw[field])

        # Relations
        for field in obj._relations.keys():
            val = raw.get(field, State.VOID)
            rel_type = obj._relations[field]['relation_type']
            rel_model = obj._parent._classes[obj._relations[field]['foreign_model']]
            if rel_type == 'm2o':
                log_load(obj, field, val, 'blue')
                typed_list = TypedList(rel_model, obj, field)
                if val is not State.VOID:
                    for rel_obj in val:
                        if isinstance(rel_obj, dict):
                            rel_obj = rel_model(**rel_obj)
                        with pretty_logger():
                            typed_list.append(rel_obj)
                    setattr(obj, field, typed_list)

            elif rel_type == 'o2m':
                if isinstance(val, dict):
                    log_load(obj, field, val, 'cyan')
                    val = rel_model(**val)
                if hasattr(val.__class__, '__bases__'):
                    if 'BaseObject' in [k.__name__ for k in val.__class__.__bases__]:
                        setattr(obj, field, val)
        return obj

    def load_raw(self, url, **kwargs):
        fn = getattr(self.session, kwargs.pop('http_method', 'get'))
        r = fn(url, params=kwargs)
        logger.debug("getting: %s" % url)
        resource = r.json(object_hook=partial(parse_custom_types, **kwargs))
        logger.debug('result: %s' % pprint.pformat(resource))
        return resource


class LoadableProperty(FilterMixIn):
    def __init__(self, attribute):
        self.attribute = attribute

    def __set__(self, obj, value):
        dirty = self.attribute in obj._dirty
        if dirty and obj._parent.state is State.LOADING:
            msg = "Not updating {}.{} as it is dirty and parent are in load state"
            logger.debug(msg.format(obj, self.attribute))
            return
        obj._values[self.attribute] = value
        if obj._parent.state is State.LOADING:
            self.status = State.LOADED
        else:
            self.status = State.DIRTY
            obj._dirty.append(self.attribute)

    def __get__(self, obj, objtype=None):
        if objtype and obj is None:
            # if parent is None, the get is invoked on class level
            # returning self will allow the user to build filters
            if self.attribute in objtype._relations:
                return RelationProperty(objtype, self.attribute)
            return self
        if self.getval(obj) is State.VOID and not obj.is_new:
            args = (obj.__class__, obj.id)
            logger.debug('Loading {} with id {} remotely'.format(*args))
            obj._parent.object_loader.load_obj(*args)
        if self.getval(obj) is State.VOID:
            return None
        return self.getval(obj)

    def getval(self, obj):
        return obj._values.get(self.attribute, State.VOID)


class RelationProperty(FilterMixIn):
    def __init__(self, parent, parent_attribute, parent_node=None):
        self.parent_klass = parent
        self.parent_attribute = parent_attribute
        self.parent_node = parent_node
        self.klass = None
        self.rel_type = None
        self.is_leaf = True
        if parent_attribute in parent._relations:
            self.rel_type = parent._relations[parent_attribute]['relation_type']
            class_name = parent._relations[parent_attribute]['foreign_model']
            self.klass = parent._parent._classes[class_name]

    def __getattr__(self, attr):
        if attr not in self.klass.attributes() and attr not in self.klass.relations():
            msg = '{} has no attribute named {}'
            raise Exception(msg.format(self.klass._class_name, attr))
        return RelationProperty(self.klass, attr, parent_node=self)

    def _assemble_filter(self, op, val):
        rfilter = ComparisonResult(self.parent_attribute, op, self._clean(val))
        if not self.is_leaf:
            return rfilter
        rp = self
        while rp.parent_node:
            rp.parent_node.is_leaf = False
            if rp.parent_node.rel_type == 'm2o':
                rfilter = rp.parent_node.any_(rfilter)
            else:
                rfilter = rp.parent_node.has_(rfilter)
            rp = rp.parent_node
        return rfilter
