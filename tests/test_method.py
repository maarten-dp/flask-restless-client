import pytest


@pytest.fixture
def apt(mcl):
    return mcl.Apartment.query.filter_by(name='ApAntMent').one()


def test_it_can_run_a_remote_method_without_params(apt):
    assert apt.function_without_params() == 5


def test_it_can_run_a_remote_method_with_builtin_type_params(apt):
    assert apt.function_with_params(5, 'test') == '5: test'


def test_it_can_run_a_remote_method_with_kwargs(apt):
    assert apt.function_with_kwargs(kwarg2=5, kwarg1='test') == 'test: 5'


def test_it_can_run_a_remote_method_with_args_kwargs(apt):
    assert apt.funtion_with_args_kwargs(arg1=5, kwarg1='test') == '5: test'


def test_it_can_run_a_remote_method_with_default_params(apt):
    assert apt.function_with_default_params(param2='test') == '5: test'


def test_it_can_run_a_remote_method_with_an_object_as_param(mcl, apt):
    colony = mcl.AntColony.get(1)
    res = apt.function_with_an_object(colony)
    assert isinstance(res, mcl.AntColony)
    assert res.name == colony.name
