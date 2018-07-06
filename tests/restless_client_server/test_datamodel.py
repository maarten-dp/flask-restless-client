import json
import flask_restless
from restless_client_server import DataModel
from flask_sqlalchemy import SQLAlchemy
from datetime import date
import pytest

def test_datamodel(app):
    db = SQLAlchemy(app)

    class Person(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.Unicode, unique=True)
        birth_date = db.Column(db.Date)


    class Computer(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.Unicode, unique=True)
        vendor = db.Column(db.Unicode)
        purchase_time = db.Column(db.DateTime)
        owner_id = db.Column(db.Integer, db.ForeignKey('person.id'))
        owner = db.relationship('Person', backref=db.backref('computers',
                                                             lazy='dynamic'))

    db.create_all()

    manager = flask_restless.APIManager(app, flask_sqlalchemy_db=db)
    manager.create_api(Person, methods=['GET'], include_columns=['name'])
    manager.create_api(Computer, methods=['GET'], collection_name='compjutahs', exclude_columns=['name'])
    data_model = DataModel(manager)
    manager.create_api(data_model, methods=['GET'])

    expected = {
        'Computer': {
            'collection_name': 'compjutahs',
            'attributes': {
                'id': 'integer',
                'owner_id': 'integer',
                'purchase_time': 'datetime',
                'vendor': 'unicode'},
            'relations': {
                'owner': {
                    'backref': 'computers',
                    'foreign_model': 'Person',
                    'relation_type': 'MANYTOONE'}},
            'methods': {}},
         'Person': {
            'collection_name': 'person',
            'attributes': {
                'name': 'unicode'},
            'relations': {},
            'methods': {}}}

    with app.app_context():
        client = app.test_client()
        res = json.loads(client.get('/api/restless-client-datamodel').data.decode('utf-8'))
    assert res == expected


def test_inheritance(app):
    db = SQLAlchemy(app)

    class Person(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        discriminator = db.Column(db.Unicode)
        __mapper_args__ = {'polymorphic_on': discriminator}

    class Engineer(Person):
        __mapper_args__ = {'polymorphic_identity': 'engineer'}
        id = db.Column(db.Integer, db.ForeignKey('person.id'), primary_key=True)
        primary_language = db.Column(db.Unicode)

    db.create_all()

    manager = flask_restless.APIManager(app, flask_sqlalchemy_db=db)
    manager.create_api(Person, methods=['GET'])
    manager.create_api(Engineer, methods=['GET'])
    data_model = DataModel(manager)
    manager.create_api(data_model, methods=['GET'])

    expected = {
        'Engineer': {
            'collection_name': 'engineer',
            'attributes': {
                'id': 'integer',
                'primary_language': 'unicode',
                'discriminator': 'unicode'},
            'relations': {},
            'methods': {}},
         'Person': {
            'collection_name': 'person',
            'attributes': {
                'id': 'integer',
                'discriminator': 'unicode'},
            'relations': {},
            'methods': {}}}

    with app.app_context():
        client = app.test_client()
        res = json.loads(client.get('/api/restless-client-datamodel').data.decode('utf-8'))
    assert res == expected


@pytest.fixture(scope='function')
def exposed_method_model_app(app):
    db = SQLAlchemy(app)

    class Person(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.Unicode, unique=True)
        birth_date = db.Column(db.Date)

        def age_in_x_years_y_months(self, y_offset, m_offset=0):
            dt = self.birth_date
            return dt.replace(
                year=dt.year + y_offset,
                month=dt.month + m_offset
            )

        def get_attrs_based_on_dict(self, args):
            return_dict = {}
            for key, val in args.items():
                if val:
                    return_dict[key] = getattr(self, key)
            return return_dict

        def what_does_this_func_even_do(self, person):
            assert isinstance(person, Person)
            return person


    db.create_all()

    db.session.add(Person(
        name='Jim Darkmagic',
        birth_date=date(2018, 1, 1)))
    db.session.commit()

    manager = flask_restless.APIManager(app, flask_sqlalchemy_db=db)
    manager.create_api(Person, methods=['GET'])
    data_model = DataModel(
        manager,
        include_model_functions=True)
    manager.create_api(data_model, methods=['GET'])
    return app


def test_exposed_methods(exposed_method_model_app):
    app = exposed_method_model_app
    with app.app_context():
        client = app.test_client()
        res = json.loads(client.get('/api/restless-client-datamodel').data.decode('utf-8'))

    expected = {
        'Person': {
            'collection_name': 'person',
            'attributes': {
                'id': 'integer',
                'name': 'unicode',
                'birth_date': 'date'},
            'relations': {},
            'methods': {
                'age_in_x_years_y_months': {
                    'required_params': ['y_offset'],
                    'optional_params': ['m_offset'],
                },
                'get_attrs_based_on_dict': {
                    'required_params': ['args'],
                    'optional_params': [],
                },
                'what_does_this_func_even_do': {
                    'required_params': ['person'],
                    'optional_params': [],
                },
            }
        }
    }
    assert res == expected

def test_call_exposed_method_int(exposed_method_model_app):
    app = exposed_method_model_app
    with app.app_context():
        client = app.test_client()
        params = '?y_offset=<int|10|>&m_offset=<int|3|>'
        url = '/api/method/person/1/age_in_x_years_y_months{}'
        res = json.loads(client.get(url.format(params)).data.decode('utf-8'))
    expected = '<date|2028-04-01|>'
    assert res == expected


def test_call_exposed_method_dict(exposed_method_model_app):
    app = exposed_method_model_app
    with app.app_context():
        client = app.test_client()
        params = '?args=<dict|<str|name|>:<bool|1|>,<str|birth_date|>:<bool|False|>|>'
        url = '/api/method/person/1/get_attrs_based_on_dict{}'
        res = json.loads(client.get(url.format(params)).data.decode('utf-8'))
    expected = '<dict|<str|name|>:<str|Jim Darkmagic|>|>'
    assert res == expected


def test_call_exposed_model_arg(exposed_method_model_app):
    app = exposed_method_model_app
    with app.app_context():
        client = app.test_client()
        params = '?person=<Person|1|>'
        url = '/api/method/person/1/what_does_this_func_even_do{}'
        res = json.loads(client.get(url.format(params)).data.decode('utf-8'))
    expected = '<Person|1|>'
    assert res == expected
