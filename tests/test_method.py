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
    colony = mcl.AntColony.get(1)
    res = mcl.Apartment.query.one().function_with_an_object(colony)
    assert isinstance(res, mcl.AntColony)
    assert res.name == colony.name
