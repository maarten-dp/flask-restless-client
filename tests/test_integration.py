import pytest

from restless_client import inspect


def test_it_can_load_an_object(cl):
    colony = cl.AntColony.query.get(1)
    assert colony.name == 'Argentine Ant'


def test_it_can_load_a_simple_filter(cl):
    colony = cl.AntColony.query.filter_by(name='Argentine Ant').one()
    assert colony.name == 'Argentine Ant'


def test_it_cant_set_an_unexisting_attribute(cl):
    colony = cl.AntColony.query.get(1)
    with pytest.raises(AttributeError):
        colony.unknown = 'Argentine Ant'


def test_it_can_load_a_simple_relation_filter(cl):
    ofilter = cl.AntColony.formicarium.name == 'Specimen-1'
    colony = cl.AntColony.query.filter(ofilter).one()
    assert colony.name == 'Argentine Ant'


def test_it_can_load_based_on_an_object_filter(cl):
    formicarium = cl.Formicarium.query.filter_by(name='Specimen-1').one()
    colony = cl.AntColony.query.filter_by(formicarium=formicarium).one()
    assert colony.name == 'Argentine Ant'


def test_it_can_init_a_polymorphed_class_correcly(cl):
    formicarium = cl.Formicarium.query.filter_by(name='Specimen-1').one()
    assert isinstance(formicarium, cl.SandwichFormicarium)
    expected = [
        'id', 'name', 'formicarium_type', 'width', 'collection_id', 'height'
    ]
    assert inspect(formicarium).attributes() == expected
    expected = ['collection', 'colonies']
    assert inspect(formicarium).relations() == expected
    assert formicarium.height == 10


def test_it_can_load_an_inherited_object(cl):
    formicarium = cl.SandwichFormicarium.query.filter_by(
        name='Specimen-1').one()
    assert formicarium.height == 10


def test_it_correctly_loads_inherited_objects(cl):
    formicaria = cl.Formicarium.query.all()
    classes = set([inspect(f).class_name for f in formicaria])
    assert set(['SandwichFormicarium', 'FreeStandingFormicarium']) == classes


def test_it_can_save_an_object(cl):
    collection = cl.AntCollection(name="Antiquities", location="The Past")
    cl.save(collection)
    assert collection.id == 4


def test_it_can_save_an_inherited_object(cl):
    formicarium = cl.SandwichFormicarium(
        name="PlAnts",
        height=10,
        width=10,
        collection=cl.AntCollection.query.get(1),
    )
    cl.save(formicarium)
    assert formicarium.id == 6


def test_it_can_save_an_object_with_an_unsaved_object_as_relation(cl):
    collection = cl.AntCollection(name="Antiquities", location="The Past")
    formicarium = cl.SandwichFormicarium(
        name="PlAnts",
        height=10,
        width=10,
        collection=collection,
    )
    cl.save(formicarium)
    assert collection.id == 4
    assert formicarium.id == 6


def test_it_can_save_an_object_with_unsaved_objects_as_relation(cl):
    formicarium = cl.SandwichFormicarium(
        name="PlAnts",
        height=10,
        width=10,
    )
    collection = cl.AntCollection(name="Antiquities",
                                  location="The Past",
                                  formicaria=[formicarium])
    cl.save(collection)
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
    cl.save(collection)
    assert collection.id == 4
    assert formicarium.id == 6


def test_it_can_update_an_object(cl, app):
    new_name = "ElephAnt"
    collection = cl.AntCollection.query.get(1)
    collection.name = new_name
    cl.save(collection)
    assert app.AntCollection.query.get(1).name == new_name


def test_it_can_update_an_object_when_removing_and_object_from_relations(
        cl, app):
    formicarium = cl.Formicarium.query.get(1)
    formicarium.colonies.remove(formicarium.colonies[0])
    cl.save(formicarium)
    assert app.Formicarium.query.get(1).colonies == []


def test_it_can_delete_an_object(cl, app):
    cl.delete(cl.AntColony.query.get(1))
    assert app.AntColony.query.get(1) is None


def test_it_can_access_a_level_two_relation(cl):
    colony = cl.AntColony.query.get(1)
    collection = colony.formicarium.collection
    assert collection.name == 'Antopia'


def test_it_can_filter_a_level_two_relation_up(cl):
    result = cl.AntColony.query.filter(
        cl.AntColony.formicarium.collection.name == 'Antics').all()
    expected = ['Fire Ant', 'Garden Ant', 'Bulldog Ant']
    assert sorted([r.name for r in result]) == sorted(expected)


def test_it_can_filter_a_level_two_relation_down(cl):
    result = cl.AntCollection.query.filter(
        cl.AntCollection.formicaria.colonies.name == 'Argentine Ant').all()
    assert result.one().name == 'Antopia'


def test_it_can_filter_boolean_expressions(cl):
    result = cl.AntColony.query.filter(
        ((cl.AntColony.name == 'Argentine Ant')
         | (cl.AntColony.queen_size > 15))
        & cl.AntColony.color.in_(['red', 'brown'])).all()
    expected = ['Fire Ant', 'Argentine Ant', 'Bulldog Ant']
    assert sorted([r.name for r in result]) == sorted(expected)


# tests not suited for this module, need to be moved
