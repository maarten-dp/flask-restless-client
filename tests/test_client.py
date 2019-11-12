import pytest
from unittest.mock import patch

import requests

from restless_client.utils import State


@patch("restless_client.ext.auth.BaseSession.request")
def test_it_set_status_back_to_loadable_if_httperror(request_method, mcl):
    apt = mcl.Apartment.get(1)

    request_method.side_effect = requests.HTTPError("Some issue")
    with pytest.raises(requests.HTTPError):
        apt.function_without_params()
    assert mcl.state == State.LOADABLE
