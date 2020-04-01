from unittest.mock import patch

import pytest
import requests

from restless_client.utils import State


@patch("restless_client.connection.Connection.request")
def test_it_set_status_back_to_loadable_if_httperror(request, mcl):
    request.side_effect = requests.HTTPError("Some issue")
    with pytest.raises(requests.HTTPError):
        apt = mcl.Apartment.query.get(1)
    assert mcl.state == State.LOADABLE
