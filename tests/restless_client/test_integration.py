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


def test_it_can_save_an_object(cl):
    collection = cl.AntCollection(
        name="Antiquities",
        location="The Past"
    )
    collection.save()
    assert collection.id == 4


def test_it_can_save_an_inherited_object(cl):
    formicarium = cl.SandwichFormicarium(
        name="PlAnts",
        height=10,
        width=10,
        collection=cl.AntCollection.get(1),
    )
    formicarium.save()
    assert formicarium.id == 6


def test_it_can_save_an_object_with_an_unsaved_object_as_relation(cl):
    collection = cl.AntCollection(
        name="Antiquities",
        location="The Past"
    )
    formicarium = cl.SandwichFormicarium(
        name="PlAnts",
        height=10,
        width=10,
        collection=collection,
    )
    formicarium.save()
    assert collection.id == 4
    assert formicarium.id == 6


def test_it_can_save_an_object_with_unsaved_objects_as_relation(cl):
    formicarium = cl.SandwichFormicarium(
        name="PlAnts",
        height=10,
        width=10,
    )
    collection = cl.AntCollection(
        name="Antiquities",
        location="The Past",
        formicaria=[formicarium]
    )
    collection.save()
    assert collection.id == 4
    assert formicarium.id == 6


def test_it_can_save_an_object_when_appending_unsaved_objects_as_relation(cl):
    formicarium = cl.SandwichFormicarium(
        name="PlAnts",
        height=10,
        width=10,
    )
    collection = cl.AntCollection(
        name="Antiquities",
        location="The Past",
    )
    collection.formicaria.append(formicarium)
    collection.save()
    assert collection.id == 4
    assert formicarium.id == 6


def test_it_can_update_an_object(cl, app):
    new_name = "ElephAnt"
    collection = cl.AntCollection.get(1)
    collection.name = new_name
    collection.save()
    assert app.AntCollection.query.get(1).name == new_name


