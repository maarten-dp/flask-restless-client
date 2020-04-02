__all__ = ('__version__', 'Client', 'inspect')

from .client import Client  # noqa F401
from .inspect import inspect  # noqa F401
from .utils import VERSION

__version__ = VERSION
