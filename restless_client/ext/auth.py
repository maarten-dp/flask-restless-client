import os
from functools import partial

import requests


class AuthenticationError(Exception):
    pass


class BaseSession(requests.Session):
    def __init__(self,
                 url=None,
                 username=None,
                 password=None,
                 token=None,
                 verify=True,
                 trust_env=True,
                 **kwargs):
        super().__init__()
        self.verify = verify
        self.trust_env = trust_env
        self.kwargs = kwargs

        if url and username:
            self.authenticate(url, username, password)
        elif url and token:
            self.authenticate(url, token)

    def authenticate(self, url, username, password=None):
        raise NotImplementedError()

    def request(self, *args, **kwargs):
        return self.validate_response(super().request(*args, **kwargs))

    def validate_response(self, res):
        # raise an exception if status is 400 or up
        try:
            json_data = res.json()
        except Exception:
            json_data = {
                'message': 'Unspecified error ({})'.format(res.content)
            }
        # prepare error message
        res.reason = "{} ({})".format(res.reason, json_data)
        # raise if needed
        res.raise_for_status()
        return res


class BasicAuthSession(BaseSession):
    def authenticate(self, url, username, password):
        self.request = partial(self.request, auth=(username, password))


class BearerSession(BaseSession):
    def __init__(self, *args, **kwargs):
        self.bearer_header = kwargs.pop('bearer_header', 'Authorization')
        self.bearer_prefix = kwargs.pop('bearer_prefix', 'Bearer')
        super().__init__(*args, **kwargs)

    def authenticate(self, url, username, password=None):
        payload = {
            self.kwargs.get('user_field', 'username'): username,
            self.kwargs.get('password_field', 'password'): password
        }
        r = self.post(url, data=payload)
        if not r.ok:
            raise AuthenticationError(r.content)
        try:
            token = r.json().get('access_token')
        except Exception as e:
            raise AuthenticationError(
                "An error occured when authenticating".format(e))

        if not token:
            msg = ('An error occurred when authenticating: %s' % r.json())
            AuthenticationError(msg)
        self.headers.update(
            {self.bearer_header: '{} {}'.format(self.bearer_prefix, token)})


def Session(*args, **kwargs):
    auth_types = {
        'basic': BasicAuthSession,
        'bearer': BearerSession,
    }
    config = {}
    for key, value in os.environ.items():
        if key.startswith('RESTLESS_CLIENT_'):
            config_key = key.replace('RESTLESS_CLIENT_', '').lower()
            config[config_key] = value

    SessionClass = auth_types[config.pop('auth_type', 'bearer')]
    kwargs.update(config)
    return SessionClass(*args, **kwargs)
