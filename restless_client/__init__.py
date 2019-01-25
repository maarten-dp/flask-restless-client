# import requests
# import pprint
# import logging
# import re
# from pytz import timezone, tzinfo, UTC
# from datetime import datetime, date
# from dateutil import parser
# from requests.packages.urllib3.exceptions import InsecureRequestWarning
# from prettytable import PrettyTable
# from functools import partial
# import json
# import time
# from collections import defaultdict

# requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
# logger = logging.getLogger('bluesnake-client')


# class UserException(Exception):
#     pass


# def clean_value(value, field_description):
#     if value and field_description == "date":
#         value = datetime.strptime(value, "%Y-%m-%d")
#     return value


# def serialize(value):
#     if isinstance(value, (date, datetime)):
#         value = value.isoformat()
#     return value


# def urljoin(*args):
#     return "/".join(args)


# LIKELY_PARSABLE_DATETIME = "^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})|(\d{8}T\d{6}Z?)"


# def datetime_from_value(value, as_timezone):
#     if isinstance(value, str) and re.search(LIKELY_PARSABLE_DATETIME, value):
#         return parser.parse(value).astimezone(as_timezone)
#     elif isinstance(value, list):
#         for idx, item in enumerate(value):
#             if isinstance(item, dict):
#                 value[idx] = parse_custom_types(item)
#             else:
#                 value[idx] = datetime_from_value(item, as_timezone)

#     return value


# def parse_custom_types(dct, as_timezone=UTC, **kwargs):
#     for k, v in dct.items():
#         try:
#             if isinstance(v, dict):
#                 dct[k] = parse_custom_types(v, as_timezone)
#             else:
#                 dct[k] = datetime_from_value(v, as_timezone)
#         except Exception:
#             pass

#     return dct


# def detect_bulk_load(inst, name, client):
#     # Sometimes you have a list of objects with unloaded relations
#     # when looping on this list and trying to access said relations
#     # you will make an http call for every relation access.
#     # in order to prevent this, we'll try to detect rapid successive
#     # calls (i.e. for loops) to unloaded relations and force a bulk load.
#     query_time = time.time()
#     detection_dict = client.bulk_load_detection[inst.__class__.__name__]
#     detection_dict.insert(0, query_time)
#     # rotate over the last 4 loads of class.attribute
#     # if the the oldest request was less than _bulk_load_time_threshold
#     # the bulk load is triggered
#     if len(detection_dict) == 4:
#         ts = detection_dict.pop()
#         limit = client._bulk_load_time_threshold
#         if query_time - ts < limit:
#             # NOTE: you could keep only the following code, but to prevent
#             # unnecessary server strain, the above was added
#             if name in inst.__class__._unloaded_relations:
#                 to_load_ids = inst.__class__._unloaded_relations[name]
#                 if to_load_ids:
#                     logger.info('Detecting rapid access to unloaded relations'
#                                 ', executing bulk load')
#                     inst.__class__.bulk_load(to_load_ids)
#                     inst.__class__._unloaded_relations[name] = set()
#                     return True
#     return False


# def load_resource(session, url, **kwargs):
#     r = session.get(url, params=kwargs)
#     logger.debug("getting: %s" % url)
#     if not r.status_code == 200:
#         msg = "Resource '%s' unavailable, recieved status code %s: %s"
#         raise Exception(msg % (url, r.status_code, r.content))
#     resource = r.json(object_hook=partial(parse_custom_types, **kwargs))
#     logger.debug('result: %s' % pprint.pformat(resource))
#     return resource


# # property to desinged to load the entire instance attributes
# def loadable_property(client, name):
#     internal_name = "_%s" % name

#     def load_property(self):
#         if not hasattr(self, internal_name) and 'C' not in str(self.id):
#             if name in self._raw_data:
#                 logger.info('USING RAW DATA %s' % name)
#                 res = self._raw_data
#             elif detect_bulk_load(self, name, client):
#                 res = self._raw_data
#             else:
#                 logger.info('LOADING PROPERTY %s' % name)
#                 res = load_resource(
#                     client.session,
#                     '%s/%s' % (self._base_url, self.id),
#                     as_timezone=client._timezone)

#             for attribute, desc in self._attrs.items():
#                 value = res.get(attribute)
#                 setattr(self, attribute, clean_value(value, desc))
#             for attribute, details in self._relations.items():
#                 value = res.get(attribute)
#                 rel_model = details['foreign_model']
#                 if value and isinstance(value, dict):
#                     value = loadable_object(client._classes[rel_model],
#                                             **value)
#                 if isinstance(value, list):
#                     val = TypedList(client._classes[rel_model], self,
#                                     attribute)
#                     for obj in value:
#                         val.append(
#                             loadable_object(client._classes[rel_model], **obj))
#                     value = val
#                 if attribute in res.keys():
#                     setattr(self, attribute, value)
#                 elif attribute not in self._raw_data.keys() and self.id:
#                     # flagging this attribute as unloaded
#                     self.__class__._unloaded_relations[attribute].add(self.id)
#                 self._raw_data.update(res)
#         return getattr(self, internal_name)

#     def overwrite_property(self, value):
#         setattr(self, internal_name, value)

#     return property(load_property, overwrite_property)


# def loadable_object(klass, **kwargs):
#     return klass(enable_load=True, **kwargs)


# def create_method_function(client, name, details):
#     method_url = details['url']

#     def fn(self, **kwargs):
#         additional = ""
#         for arg in details['args']:
#             additional += "/%s" % kwargs[arg]
#         if isinstance(self.id, str) and self.id.startswith('C'):
#             raise Exception('Cannot use methods on newly created objects')
#         url_params = {
#             'target': self.__class__.__name__.lower(),
#             'oid': self.id,
#             'method': name,
#             'additional': additional
#         }
#         suffix = method_url.format(**url_params)
#         if suffix.startswith("/"):
#             suffix = suffix[1:]
#         url = urljoin(client.model_url, suffix)
#         return load_resource(
#             client.session, url, as_timezone=client._timezone, **kwargs)

#     return fn


# class TypedList(list):
#     def __init__(self, otype, parent, for_attr=None):
#         self.type = otype
#         self.parent = parent
#         self.for_attr = for_attr

#     def append(self, item):
#         self.parent._dirty = True
#         cls_name = item.__class__.__name__
#         if not isinstance(item, self.type):
#             msg = 'Only {} can be added, {} provided'
#             raise TypeError(msg.format(self.type.__name__, cls_name))
#         if item in self:
#             msg = 'Object {} with id {} is already in this list'
#             raise UserException(msg.format(self.type.__name__, item.id))
#         super(TypedList, self).append(item)
#         if self.for_attr:
#             self._update_backref(item, self.for_attr)

#     def _update_backref(self, item, attr, remove=False):
#         rel_details = self.parent._relations[attr]
#         backref = rel_details.get('backref')
#         if backref:
#             msg = 'Updating backref {} for {}'
#             logger.debug(msg.format(rel_details['backref'], item))
#             if item._relations[backref]['relation_type'] == 'o2m':
#                 value = self.parent
#                 if remove:
#                     value = None
#                 setattr(item, rel_details['backref'], value)
#                 item._dirty = True
#             if item._relations[backref]['relation_type'] == 'm2o':
#                 internal_attr = '_{}'.format(rel_details['backref'])
#                 if hasattr(item, internal_attr):
#                     lst = getattr(item, internal_attr)
#                     if remove:
#                         if self.parent in lst:
#                             list.remove(lst, self.parent)
#                     else:
#                         if self.parent not in lst:
#                             list.append(lst, self.parent)
#                     item._dirty = True

#     def remove(self, item):
#         super(TypedList, self).remove(item)
#         self.parent._dirty = True
#         if self.for_attr:
#             self._update_backref(item, self.for_attr, remove=True)


# # only used for printing puroposes, has no functional benefit
# class ObjectCollection(list):
#     def __init__(self, object_class, lst=None, attrs=None):
#         self.object_class = object_class
#         self.attrs = attrs or object_class.attrs()
#         if lst:
#             self.extend(lst)

#     def first(self):
#         return self[0]

#     def one(self):
#         if len(self) > 1:
#             raise ValueError('more than one result')
#         return self.first()

#     def __getitem__(self, key):
#         if isinstance(key, int):
#             return list.__getitem__(self, key)
#         if isinstance(key, str):
#             key = [key]
#         return ObjectCollection(self.object_class, self, attrs=key)

#     def pprint(self):
#         attrs = self.attrs
#         # make sure id and name are at the front of the table
#         headers = ['id']
#         if 'name' in attrs:
#             headers.append('name')
#         columns = set(attrs).difference(set(['id', 'name']))
#         relation_columns = [c for c in columns if str(c).endswith('_id')]
#         data_columns = columns.difference(set(relation_columns))
#         # make sure to show the data columns next
#         headers.extend(sorted(data_columns))
#         # then show relation columns
#         headers.extend(sorted(relation_columns))
#         pt = PrettyTable(headers)
#         pt.align = 'l'
#         for obj in self:
#             pt.add_row([obj._raw_data.get(header) for header in headers])
#         res = pt.get_string(border=False, sortby="id")
#         if not res:
#             pt.add_row(['' for header in headers])
#             res = pt.get_string(border=False, sortby="id")
#         return res

#     def __repr__(self):
#         return self.pprint()


# class Client(object):
#     def __init__(self, url, session=None,
#                  debug=None,
#                  timezone=None,
#                  model_root="",
#                  **kwargs):
#         self.base_url = url
#         self.model_url = url
#         if model_root:
#             if 'http' in model_root:
#                 self.model_url = model_root
#             else:
#                 self.model_url = urljoin(url, model_root)
#         self.registry = {}
#         self.created = 0
#         self._authenticated = False
#         self._classes = {}
#         self.timezone = timezone
#         self.bulk_load_detection = defaultdict(list)
#         # Sets the time threshold the system uses to do it's bulk load detection
#         # Set to avg_http_response_time * 3 for slow connections
#         self._bulk_load_time_threshold = 1
#         self._bulk_load_chunk_size = 50

#         if debug:
#             logger.addHandler(logging.StreamHandler())
#             try:
#                 logger.setLevel(debug)
#             except Exception:
#                 logger.setLevel(logging.DEBUG)

#         if not session:
#             session = requests.Session()
#         self.session = session
#         if kwargs:
#             self.authenticate(**kwargs)

#     def initialise(self, model_path='datamodel'):
#         if not self._authenticated:
#             msg = ('The client is not yet authenticated. '
#                    'call client.authenticate() to log in.')
#             UserException(msg)
#         res = load_resource(self.session, urljoin(self.base_url, model_path))
#         for name, details in res.items():
#             self._construct_class(name, details)

#     def authenticate(self, initialise=True, **kwargs):
#         r = self.session.post(urljoin(self.base_url, 'auth'), data=kwargs)
#         if not r.ok:
#             raise UserException(r.content)
#         try:
#             token = r.json().get('access_token')
#         except Exception as e:
#             raise UserException(
#                 "An error occured when authenticating".format(e))

#         if not token:
#             msg = ('An error occurred when authenticating: %s' % r.json())
#             UserException(msg)
#         self.session.headers.update({
#             'Authorization': 'Bearer {}'.format(token)
#         })
#         self._authenticated = True
#         if initialise:
#             self.initialise()

#     @property
#     def timezone(self):
#         return self._timezone

#     @timezone.setter
#     def timezone(self, tz):
#         if tz is None:
#             self._timezone = UTC
#         elif isinstance(tz, tzinfo.tzinfo):
#             self._timezone = tz
#         else:
#             self._timezone = timezone(tz)

#     def classes(self):
#         return self._classes.keys()

#     def _construct_class(self, name, details):
#         attributes = {
#             '_parent': self,
#             '_class_name': name,
#             '_attrs': details['attributes'],
#             '_relations': details['relations'],
#             '_methods': details['methods'].keys(),
#             '_base_url': urljoin(self.model_url, name.lower()),
#         }
#         for field in details['attributes']:
#             if field == 'id':
#                 continue
#             attributes[field] = loadable_property(self, field)
#         for field in details['relations']:
#             attributes[field] = loadable_property(self, field)
#         # construct methods
#         for method, method_details in details['methods'].items():
#             attributes[method] = create_method_function(
#                 self, method, method_details)

#         klass = type(str(name), (BaseObject, ), attributes)
#         self._classes[name] = klass
#         setattr(self, name, klass)

#     def _register(self, obj):
#         self.registry['%s%s' % (obj.__class__.__name__, obj.id)] = obj

#     def save(self):
#         for obj in self.registry.values():
#             if obj._dirty:
#                 obj.save()

#     def _generate_temp_id(self):
#         self.created += 1
#         return "C%s" % self.created


# class BaseObject(object):
#     _attrs = {}
#     _relations = {}
#     _base_url = None
#     _class_name = None
#     _unloaded_relations = defaultdict(set)

#     def __setattr__(self, name, value):
#         if name in self._relations.keys():
#             rel_type = self._relations[name]['relation_type']
#             rel_model = self._relations[name]['foreign_model']
#             if value and rel_type == 'o2m':
#                 if value.__class__ not in (self._parent._classes[rel_model],
#                                            property):
#                     msg = '%s must be an instance of %s, not %s'
#                     raise Exception(msg % (name, rel_model,
#                                            value.__class__.__name__))
#         if not self._dirty:
#             object.__setattr__(self, '_dirty', True)
#         object.__setattr__(self, name, value)

#     def __new__(cls, **kwargs):
#         key = None
#         if kwargs.get('id'):
#             key = '%s%s' % (cls.__name__, kwargs['id'])
#         return cls._parent.registry.get(key, object.__new__(cls))

#     def __init__(self, enable_load=False, **kwargs):
#         # check if the instance has already been initialised
#         object.__setattr__(self, '_dirty', False)
#         is_new = 'id' not in kwargs
#         kwargs['id'] = kwargs.get('id', self._parent._generate_temp_id())
#         if not hasattr(self, '_raw_data'):
#             object.__setattr__(self, '_raw_data', {})
#         if not hasattr(self, 'id'):
#             object.__setattr__(self, '_raw_data', kwargs)
#             logger.debug('MAKING NEW %s' % self.__class__.__name__)
#             # setting all attributes
#             for field, desc in self._attrs.items():
#                 val = kwargs.get(field)
#                 if val or not enable_load:
#                     setattr(self, field, clean_value(val, desc))
#             # setting all relations
#             for field in self._relations.keys():
#                 val = kwargs.get(field)
#                 rel_type = self._relations[field]['relation_type']
#                 rel_model = self._relations[field]['foreign_model']
#                 if rel_type == 'm2o':
#                     objects = val
#                     val = TypedList(self._parent._classes[rel_model], self,
#                                     field)
#                     if field in kwargs.keys():
#                         assert isinstance(objects, list)
#                         for obj in objects:
#                             if isinstance(obj, dict):
#                                 rel_class = self._parent._classes[rel_model]
#                                 obj = loadable_object(rel_class, **obj)
#                             val.append(obj)
#                         setattr(self, field, val)
#                     elif objects is None and is_new:
#                         setattr(self, field, val)
#                 elif rel_type == 'o2m':
#                     id_field = '{}_id'.format(field)
#                     if isinstance(val, dict):
#                         val = self._parent._classes[rel_model](**val)
#                     elif isinstance(val, BaseObject):
#                         setattr(self, field, val)
#                     elif val is None and id_field not in kwargs.keys(
#                     ) and is_new:
#                         setattr(self, field, val)
#                 if field not in kwargs.keys() and self.id and not is_new:
#                     # flagging this attribute as unloaded
#                     self.__class__._unloaded_relations[field].add(self.id)
#             self._parent._register(self)
#             object.__setattr__(self, '_dirty', False)
#             if isinstance(self.id, str) and self.id.startswith("C"):
#                 object.__setattr__(self, '_dirty', True)
#         else:
#             kwargs.update(self._raw_data)
#             object.__setattr__(self, '_raw_data', kwargs)
#             logger.debug('USING EXISTING %s' % self.__class__.__name__)

#     @classmethod
#     def all(cls):
#         client = cls._parent
#         session = client.session
#         tz = client._timezone
#         result = load_resource(session, cls._base_url, as_timezone=tz)
#         objects = result['objects']
#         for page in range(2, result['total_pages'] + 1):
#             result = load_resource(
#                 session, cls._base_url, page=page, as_timezone=tz)
#             objects.extend(result['objects'])
#         # There is an issue on the server regarding pagination.
#         # It returns the same object on subsequent pages.
#         # Fixing this by casting to a set.
#         return ObjectCollection(cls, set([cls(**obj) for obj in objects]))

#     @classmethod
#     def get(cls, oid):
#         client = cls._parent
#         session = client.session
#         tz = client._timezone
#         # try to use cache
#         registry_id = '{}{}'.format(cls.__name__, oid)
#         if registry_id in client.registry:
#             return client.registry[registry_id]
#         obj = load_resource(
#             session, '%s/%s' % (cls._base_url, oid), as_timezone=tz)
#         return cls(**obj)

#     @classmethod
#     def bulk_load(cls, oids):
#         results = []
#         chunk_size = cls._parent._bulk_load_chunk_size
#         oids = list(oids)
#         for i in range(0, len(oids), chunk_size):
#             chunk = oids[i:i + chunk_size]
#             results.append(cls.filter(('id', 'in', list(chunk))))

#     @classmethod
#     def filter(cls, *raw_filters):
#         filters = []
#         msg = ("%s has no field named %s and relational searches are"
#                " not supported yet")
#         for f in raw_filters:
#             if not f[0] in cls.attrs():
#                 raise Exception(msg % (cls.__name__, f[0]))
#             filters.append({"name": f[0], "op": f[1], "val": f[2]})
#         query = json.dumps({'filters': filters})

#         session = cls._parent.session
#         tz = cls._parent._timezone
#         result = load_resource(session, cls._base_url, q=query, as_timezone=tz)
#         objects = result['objects']
#         for page in range(2, result['total_pages'] + 1):
#             result = load_resource(
#                 session, cls._base_url, q=query, as_timezone=tz, page=page)
#             objects.extend(result['objects'])
#         # There is an issue on the server regarding pagination.
#         # It returns the same object on subsequent pages.
#         # Fixing this by casting to a set.
#         return ObjectCollection(cls, set([cls(**obj) for obj in objects]))

#     @classmethod
#     def attrs(cls):
#         return cls._attrs.keys()

#     @classmethod
#     def relations(cls):
#         return cls._relations.keys()

#     @classmethod
#     def methods(cls):
#         return cls._methods

#     def delete(self):
#         if not self.is_new_object():
#             url = '%s/%s' % (self._base_url, self.id)
#             r = self._parent.session.delete(url)
#             if not r.status_code == 204:
#                 msg = "Unable to delete object %s, recieved status code %s: %s"
#                 raise Exception(msg % (self.__class__.__name__, r.status_code,
#                                        r.content))
#         return True

#     def is_new_object(self):
#         return 'C' in str(self.id)

#     def _flat_dict(self):
#         # create attribute dict
#         object_dict = {}

#         def is_loaded(obj, attr):
#             internal_name = '_{}'.format(attr)
#             return hasattr(obj, internal_name)

#         for field in self._attrs:
#             if not is_loaded(self, field):
#                 continue
#             val = getattr(self, field, None)
#             # check if we want to set the value to None if the value is None
#             # by checking what the initial value was
#             if val is not None or self._raw_data.get(field) is not None:
#                 object_dict[field] = serialize(val)
#         if 'id' in object_dict:
#             object_dict.pop('id')

#         # add relation ids
#         for field, details in self._relations.items():
#             if not is_loaded(self, field):
#                 continue
#             obj = getattr(self, field, None)
#             if details['relation_type'] == 'o2m':
#                 if obj:
#                     # save new objects, that this object relies on, first
#                     if obj.is_new_object():
#                         obj.save()
#                     object_dict["{}_id".format(field)] = obj.id
#                 elif self._raw_data.get(field):
#                     object_dict["{}_id".format(field)] = None
#             if details['relation_type'] == 'm2o':
#                 if obj:
#                     ids = []
#                     for item in obj:
#                         if item.is_new_object():
#                             item.save()
#                         ids.append({'id': item.id})
#                     object_dict[field] = ids
#                 elif self._raw_data.get(field):
#                     object_dict[field] = []

#         return object_dict

#     def save(self):
#         if self.is_new_object():
#             self._create()
#         elif self._dirty:
#             self._update()
#         else:
#             logger.debug("No action needed")
#         object.__setattr__(self, '_dirty', False)

#     def _create(self):
#         object_dict = self._flat_dict()
#         logger.debug("Creating: %s" % self._base_url)
#         logger.debug("Body: %s" % object_dict)
#         r = self._parent.session.post(self._base_url, json=object_dict)
#         if r.ok:
#             self.id = r.json()['id']
#         else:
#             msg = "Unable to create object %s, recieved status code %s: %s"
#             raise Exception(msg % (self.__class__.__name__, r.status_code,
#                                    r.content))

#     def _update(self):
#         object_dict = self._flat_dict()
#         url = urljoin(self._base_url, str(self.id))
#         logger.debug("Updating: %s" % url)
#         logger.debug("Body: %s" % object_dict)
#         r = self._parent.session.put(url, json=object_dict)
#         if not r.ok:
#             msg = "Unable to update object %s, recieved status code %s: %s"
#             raise Exception(msg % (self.__class__.__name__, r.status_code,
#                                    r.content))

#     def refresh(self):
#         for field in list(self.attrs()) + list(self.relations()):
#             internal_name = '_{}'.format(field)
#             if hasattr(self, internal_name):
#                 delattr(self, internal_name)
#         self._raw_data = {}

#     def __repr__(self):
#         attributes = ["id: %s" % self.id]
#         if hasattr(self, 'name'):
#             attributes.append("name: %s" % self.name)
#         return "<%s [%s]>" % (self.__class__.__name__, " | ".join(attributes))
