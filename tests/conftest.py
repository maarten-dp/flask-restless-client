import os
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from multiprocessing import Process

import cereal_lazer
import flask_restless
import pytest
from fast_alchemy import FlaskFastAlchemy
from flask import Flask
from flask_restless_datamodel import DataModel
from flask_sqlalchemy import SQLAlchemy
from requests_flask_adapter import Session
from sqlalchemy.ext.hybrid import hybrid_property

from restless_client import Client
from restless_client.ext.auth import BaseSession

ROOT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(ROOT_DIR, 'data')
API_METHODS = ['GET', 'PUT', 'POST', 'DELETE']


class RaiseSession(BaseSession, Session):
    def request(self, *args, **kwargs):
        return super().request(*args, **kwargs)


def build_endpoints(app, fa):
    manager = flask_restless.APIManager(app, flask_sqlalchemy_db=app.db)
    for class_name, class_ in fa.class_registry.items():
        manager.create_api(class_, methods=API_METHODS)
        setattr(app, class_name, class_)
    data_model = DataModel(manager)
    manager.create_api(data_model, methods=['GET'])
    app.manager = manager


@pytest.fixture(scope='function')
def app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///:memory:"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['PROPAGATE_EXCEPTIONS'] = True
    db = SQLAlchemy(app)
    app.db = db
    return app


@pytest.fixture(scope='function')
def session(app):
    return app.db.session


@pytest.fixture(scope='function')
def instances(app):
    fa = FlaskFastAlchemy(app.db)
    fa.load(os.path.join(DATA_DIR, 'instances.yaml'))
    build_endpoints(app, fa)
    return fa


@pytest.fixture(scope='function')
def filters(app):
    fa = FlaskFastAlchemy(app.db)
    fa.load(os.path.join(DATA_DIR, 'filter.yaml'))
    build_endpoints(app, fa)
    return app


@pytest.fixture
def cl(app, instances):
    RaiseSession.register('http://app', app)
    return Client(url='http://app/api', session=RaiseSession(), debug=True)


@pytest.fixture
def fcl(filters):
    RaiseSession.register('http://app', filters)
    return Client(url='http://app/api', session=RaiseSession(), debug=True)


@pytest.fixture
def mcl(app, session, instances):
    db = app.db

    class MisterTyper(db.Model):
        __tablename__ = "mister_typer"
        id = db.Column(db.Integer, primary_key=True)
        date = db.Column(db.Date())
        dt = db.Column(db.DateTime())
        json = db.Column(db.JSON())
        interval = db.Column(db.Interval())
        binary = db.Column(db.Binary())
        num = db.Column(db.Numeric())

    db.create_all()

    class Apartment(instances.Formicarium):
        __mapper_args__ = {'polymorphic_identity': 'apartment'}

        @property
        def some_property(self):
            return 'a_property_value'

        @hybrid_property
        def some_hybrid(self):
            return self.collection

        def function_without_params(self):
            return 5

        def function_with_params(self, arg1, arg2):
            return '{}: {}'.format(arg1, arg2)

        def function_with_kwargs(self, kwarg1, kwarg2):
            return self.function_with_params(kwarg1, kwarg2)

        def funtion_with_args_kwargs(self, arg1, kwarg1):
            return self.function_with_params(arg1, kwarg1)

        def function_with_default_params(self, param1=5, param2=6):
            return self.function_with_params(param1, param2)

        def function_with_an_object(self, obj):
            assert isinstance(obj, app.AntColony)
            return obj

        def function_with_uncommitted_object(self):
            return Apartment(name='Oof-Owie')

        def function_with_new_obj(self):
            mt = MisterTyper(
                date=date(2018, 1, 1),
                dt=datetime(2018, 1, 1),
                json={"awe": "some"},
            )
            session.add(mt)
            session.commit()
            return mt

    Apartment.__tablename__ = 'apartment'

    apt = Apartment(name='ApAntMent')
    apt.collection = instances.AntCollection.query.first()
    session.add(apt)
    session.commit()

    app.manager.create_api(Apartment, methods=API_METHODS)
    app.manager.create_api(MisterTyper, methods=API_METHODS)

    RaiseSession.register('http://app', app)

    yield Client(url='http://app/api', session=RaiseSession(), debug=True)
