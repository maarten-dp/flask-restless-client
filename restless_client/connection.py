import logging
import pprint
from functools import partial, wraps

import requests
from ordered_set import OrderedSet
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from .utils import parse_custom_types, urljoin

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
logger = logging.getLogger('restless-client')


def get_url(obj):
    return obj._rlc.base_url


def log(fn):
    @wraps(fn)
    def decorator(*args, **kwargs):
        logger.debug('kwargs: {}'.format(pprint.pformat(kwargs)))
        res = fn(*args, **kwargs)
        logger.debug('result: {}'.format(pprint.pformat(res)))
        return res

    return decorator


def lock_loading(fn):
    @wraps(fn)
    def decorator(self, obj, *args, **kwargs):
        with obj._rlc.client.loading:
            return fn(self, obj, *args, **kwargs)

    return decorator


def raise_on_locked(fn):
    def decorator(self, obj, *args, **kwargs):
        """
        mostly a utility and debugging measure. We'd like to prevent a load from
        being triggered when another load is in progress. Throwing a hard
        exception will give us a handle on the problem much faster.
        """
        client = obj._rlc.client
        if client.is_loading and client.opts.debug:
            raise Exception('Loading is locked')
        return fn(self, obj, *args, **kwargs)

    return decorator


class Connection:
    def __init__(self, client, opts):
        self.client = client
        self.session = opts.session
        self.opts = opts

    @raise_on_locked
    @lock_loading
    def load_query(self, obj_class, single=False, **kwargs):
        raw = self.request(obj_class._rlc.base_url, params=kwargs)

        if single:
            return obj_class(**raw)

        # iterate over pages
        objects = raw['objects']
        for page in range(2, raw['total_pages'] + 1):
            kwargs['page'] = page
            objects.extend(
                self.request(obj_class._rlc.base_url,
                             params=kwargs)['objects'])

        return self.opts.CollectionClass(
            obj_class, OrderedSet([obj_class(**obj) for obj in objects]))

    @raise_on_locked
    @lock_loading
    def load(self, obj_class, obj_id):
        raw = self.request(urljoin(obj_class._rlc.base_url, str(obj_id)))
        return obj_class(**raw)

    @lock_loading
    def create(self, obj, object_dict=None):
        object_dict = object_dict or self.client.serializer.serialize_dirty(
            obj)

        property_values = {}
        for property_name in obj._rlc.dirty_properties:
            property_values[property_name] = object_dict.pop(property_name)

        url = obj._rlc.base_url
        r = self.request(url, http_method='post', json=object_dict)
        setattr(obj, obj._rlc.pk_name, r[obj._rlc.pk_name])

    @lock_loading
    def update(self, obj, object_dict=None):
        object_dict = object_dict or self.client.serializer.serialize_dirty(
            obj)
        url = urljoin(obj._rlc.base_url, str(obj._rlc.pk_val))
        self.request(url, http_method='put', json=object_dict)

    def delete(self, obj):
        if not obj._rlc.is_new:
            url = urljoin(obj._rlc.base_url, str(obj._rlc.pk_val))
            self.request(url, http_method='delete')

    @log
    def request(self, url, **kwargs):
        method = kwargs.pop('http_method', 'get')
        fn = getattr(self.session, method)
        r = fn(url, **kwargs)
        if method == 'delete':
            return

        result = r.json(object_hook=partial(parse_custom_types, **kwargs), )
        return result
