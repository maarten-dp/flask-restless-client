import requests

# def test_attributes(cl):
#     obj = cl.Object1.get(2)
#     assert obj.attribute1 == 'o1a12'
#     assert obj.attribute2 == 2
#     assert obj.attribute3 == 'o1a32'
#     assert cl._session.called['get'] == 1


# def test_relation(cl):
#     obj = cl.Object1.get(2)
#     assert obj.relation1[0].attribute1 == 'o2a11'
#     assert cl._session.called['get'] == 1


# def test_it_loads_unloaded_relations(cl):
#     obj = cl.Object1.get(2)
#     assert obj.relation2.relation2[0].attribute1 == 'o2a11'
#     assert cl._session.called['get'] == 2


def test_request(runserver):
    assert b'test' == requests.get('http://localhost:5000/').content