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


def test_it_can_run_a_remote_method_returning_uncommitted_obj(mcl):
    res = mcl.Apartment.query.one().function_with_uncommitted_object()
    assert isinstance(res, mcl.Apartment)
    assert res.name == 'Oof-Owie'
    assert not res._pkval


def test_it_can_get_a_remote_property(mcl):
    assert mcl.Apartment.query.one().some_property == 'a_property_value'


def test_it_can_get_a_remote_hybrid_property(mcl):
    # Fill colonies of apt
    colonies = mcl.AntColony.query.all()
    apt = mcl.Apartment.query.one()
    apt.colonies = colonies
    apt.save()

    # Refresh it
    apt = mcl.Apartment.query.one()
    assert apt.some_hybrid_property == apt.colonies
