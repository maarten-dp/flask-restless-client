import inspect

from .utils import State


def construct_method(opts, client, method, method_details):
    method = opts.Method(method, method_details, client.connection)

    def func(self, *args, **kwargs):
        return method(self, *args, **kwargs)

    # code = func.__code__
    # func = types.FunctionType(code, func.__globals__, method.name)
    params = []
    for param in method_details['args']:
        params.append(
            inspect.Parameter(param, inspect.Parameter.POSITIONAL_OR_KEYWORD))

    for param in method_details['kwargs']:
        params.append(
            inspect.Parameter(param,
                              inspect.Parameter.POSITIONAL_OR_KEYWORD,
                              default=State.VOID))

    func.__signature__ = inspect.Signature(params)
    func.__name__ = method.name
    return func


class Method:
    def __init__(self, name, details, connection):
        self.name = name
        self.connection = connection
        self.args = details['args']
        self.kwargs = details['kwargs']
        self.argsvar = details['argsvar']
        self.kwargsvar = details['kwargsvar']

    def __call__(self, obj, *args, **kwargs):
        self.validate_params(args, kwargs)
        rlc = obj._rlc
        url = '{}/{}/{}'.format(rlc.method_url, rlc.pk_val, self.name)
        payload = {'payload': self.serialize_params(args, kwargs)}
        result = self.connection.request(url, http_method='post', json=payload)
        result = self.cereal.loads(result['payload'])
        return result

    @property
    def cereal(self):
        return self.connection.client.cereal

    def serialize_params(self, args, kwargs):
        return self.cereal.dumps({'args': args, 'kwargs': kwargs})

    def validate_params(self, args, kwargs):
        if not self.argsvar and len(args) < len(self.args):
            msg = '{}() missing {} required positional argument: {}'
            diff = self.args[len(args):]
            TypeError(msg.format(self.name, len(diff), ', '.join(diff)))
        kwdiff = set(self.kwargs).difference(kwargs.keys())
        if not self.kwargsvar and kwdiff:
            msg = "{}() got an unexpected keyword argument '{}'"
            TypeError(msg.format(self.name, kwdiff.pop()))

        for key, val in list(kwargs.items()):
            if val == State.VOID:
                kwargs.pop(key)
