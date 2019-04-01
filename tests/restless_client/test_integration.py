import requests


def test_it_can_load_an_object(cl):
    colony = cl.AntColony.get(1)
    assert colony.name == 'Argentine Ant'


def test_it_can_load_a_simple_filter(cl):
    colony = cl.AntColony.query.filter_by(name='Argentine Ant').one()
    assert colony.name == 'Argentine Ant'


def test_it_can_load_a_simple_relation_filter(cl):
    ofilter = cl.AntColony.formicarium.name == 'Specimen-1'
    colony = cl.AntColony.query.filter(ofilter).one()
    assert colony.name == 'Argentine Ant'


def test_it_can_load_based_on_an_object_filter(cl):
    formicarium = cl.Formicarium.query.filter_by(name='Specimen-1').one()
    colony = cl.AntColony.query.filter_by(formicarium=formicarium).one()
    assert colony.name == 'Argentine Ant'


def test_it_can_load_an_inherited_object(cl):
    formicarium = cl.SandwichFormicarium.query.filter_by(name='Specimen-1').one()
    assert formicarium.height == 10
