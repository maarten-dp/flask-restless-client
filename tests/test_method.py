from collections import defaultdict
from datetime import date, datetime, timedelta

from restless_client import types
from restless_client.inspect import inspect


def test_it_can_run_a_remote_method_without_params(mcl):
    res = mcl.Apartment.query.one().function_without_params()
    assert res == 5


def test_it_can_run_a_remote_method_with_builtin_type_params(mcl):
    res = mcl.Apartment.query.one().function_with_params(5, 'test')
    assert res == '5: test'


def test_it_can_run_a_remote_method_with_kwargs(mcl):
    res = mcl.Apartment.query.one().function_with_kwargs(kwarg2=5,
                                                         kwarg1='test')
    assert res == 'test: 5'


def test_it_can_run_a_remote_method_with_args_kwargs(mcl):
    res = mcl.Apartment.query.one().funtion_with_args_kwargs(arg1=5,
                                                             kwarg1='test')
    assert res == '5: test'


def test_it_can_run_a_remote_method_with_default_params(mcl):
    res = mcl.Apartment.query.one().function_with_default_params(param2='test')
    assert res == '5: test'


def test_it_can_run_a_remote_method_with_an_object_as_param(mcl):
    colony = mcl.AntColony.query.get(1)
    res = mcl.Apartment.query.one().function_with_an_object(colony)
    assert isinstance(res, mcl.AntColony)
    assert res.name == colony.name


def test_it_can_run_a_remote_method_returning_uncommitted_obj(mcl):
    res = mcl.Apartment.query.one().function_with_uncommitted_object()
    assert isinstance(res, mcl.Apartment)
    assert res.name == 'Oof-Owie'
    assert not inspect(res).pk_val


def test_it_can_get_a_remote_property(mcl):
    assert mcl.Apartment.query.one().some_property == 'a_property_value'


def test_it_can_set_a_remote_property(mcl):
    apt = mcl.Apartment.query.one()
    assert apt.settable_property == 'ApAntMent'
    apt.settable_property = 'ApSetMent'
    mcl.save(apt)
    assert mcl.Apartment.query.one().settable_property == 'ApSetMent'


def test_it_casts_attribute_types_correctly_when_not_marshalling_from_json(
        mcl):
    apt = mcl.Apartment.query.one()
    mt = apt.function_with_new_obj()

    expected_types = {
        "date": date,
        "dt": datetime,
        "json": dict,
    }
    for key, type_ in expected_types.items():
        assert type(getattr(mt, key)) == type_


def test_it_can_execute_an_object_hook(mcl):
    types.OBJECT_HOOKS = defaultdict(dict)

    @types.object_hook(mcl.Apartment.some_hybrid)
    def hybrid_parser(value):
        return mcl.AntCollection(**value)

    apt = mcl.Apartment.query.one()
    assert apt.some_hybrid.__class__ == mcl.AntCollection


def test_it_can_execute_an_object_hook_defined_as_strings(mcl):
    types.OBJECT_HOOKS = defaultdict(dict)

    @types.object_hook('Apartment', 'some_hybrid')
    def hybrid_parser(value):
        return mcl.AntCollection(**value)

    apt = mcl.Apartment.query.one()
    assert apt.some_hybrid.__class__ == mcl.AntCollection
