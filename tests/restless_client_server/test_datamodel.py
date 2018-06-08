import json
import flask_restless
from restless_client_server import DataModel
from flask_sqlalchemy import SQLAlchemy

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
    manager.create_api(data_model, methods=['GET'], preprocessors=data_model.processors)

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
                    'relation_type': 'MANYTOONE'}}},
         'Person': {
            'collection_name': 'person',
            'attributes': {
                'name': 'unicode'},
            'relations': {}}}

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
    manager.create_api(data_model, methods=['GET'], preprocessors=data_model.processors)

    expected = {
        'Engineer': {
            'collection_name': 'engineer',
            'attributes': {
                'id': 'integer',
                'primary_language': 'unicode',
                'discriminator': 'unicode'},
            'relations': {}},
         'Person': {
            'collection_name': 'person',
            'attributes': {
                'id': 'integer',
                'discriminator': 'unicode'},
            'relations': {}}}

    with app.app_context():
        client = app.test_client()
        res = json.loads(client.get('/api/restless-client-datamodel').data.decode('utf-8'))
    from pprint import pprint
    pprint(res)
    assert res == expected