import requests
import pprint
import logging
from restless_client.utils import (parse_custom_types, urljoin, ObjectCollection)
import crayons
from functools import partial
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
import json
from collections import OrderedDict
from ordered_set import OrderedSet

logger = logging.getLogger('restless-client')


def log(fn):
    def decorator(*args, **kwargs):
        logger.debug('kwargs: {}'.format(pprint.pformat(kwargs)))
        res = fn(*args, **kwargs)
        logger.debug('result: {}'.format(pprint.pformat(res)))
        return res
    return decorator


def lock_loading(fn):
    def decorator(self, obj, *args, **kwargs):
        with obj._client.loading:
            return fn(self, obj, *args, **kwargs)
    return decorator


class RestlessError(Exception):
    pass


class Connection:
    def __init__(self, session, opts):
        self.session = session
        self.opts = opts

    @lock_loading
    def load_query(self, obj_class, single=False, **kwargs):
        raw = self.request(obj_class._base_url, **kwargs)

        if single:
            return obj_class(**raw)

        # iterate over pages
        objects = raw['objects']
        for page in range(2, raw['total_pages'] + 1):
            kwargs['page'] = page
            objects.extend(self.request(obj_class._base_url, **kwargs)['objects'])

        return self.opts.CollectionClass(
            obj_class, OrderedSet([obj_class(**obj) for obj in objects]))

    @lock_loading
    def load(self, obj_class, obj_id):
        raw = self.request(urljoin(obj_class._base_url, str(obj_id)))
        return obj_class(**raw)

    @lock_loading
    def create(self, obj, object_dict=None):
        object_dict = object_dict or obj._flat_dict()
        r = self.request(obj._base_url, http_method='post', json=object_dict)
        obj._pkval = r.json()[obj._pk_name]

    @lock_loading
    def update(self, obj, object_dict=None):
        object_dict = object_dict or obj._flat_dict()
        url = urljoin(obj._base_url, str(obj._pkval))
        self.request(url, http_method='put', json=object_dict)

    @log
    def request(self, url, **kwargs):
        fn = getattr(self.session, kwargs.pop('http_method', 'get'))
        r = fn(url, params=kwargs)
        result = r.json(
            object_hook=partial(parse_custom_types, **kwargs),
            # object_pairs_hook=OrderedDict
        )

        if 'message' in result:
            raise RestlessError(result['message'])
        return result
