import time
import pytest
import flask_restless
from flask import Flask
from multiprocessing import Process
from flask_sqlalchemy import SQLAlchemy
from fast_alchemy import FlaskFastAlchemy
from restless_client import Client
from restless_client_server import DataModel
from requests_flask_adapter import Session
import os

ROOT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(ROOT_DIR, 'data')


def build_endpoints(app, fa):
    manager = flask_restless.APIManager(app, flask_sqlalchemy_db=app.db)
    for class_ in fa.class_registry.values():
        manager.create_api(class_, methods=['GET'])
    data_model = DataModel(manager)
    manager.create_api(data_model, methods=['GET'])


@pytest.fixture(scope='function')
def app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///:memory:"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db = SQLAlchemy(app)
    app.db = db
    return app


@pytest.fixture(scope='function')
def instances(app):
    fa = FlaskFastAlchemy(app.db)
    fa.load(os.path.join(DATA_DIR, 'instances.yaml'))
    build_endpoints(app, fa)
    return app


@pytest.fixture(scope='function')
def filters(app):
    fa = FlaskFastAlchemy(app.db)
    fa.load(os.path.join(DATA_DIR, 'filter.yaml'))
    build_endpoints(app, fa)
    return app


@pytest.fixture
def cl(instances):
    Session.register('http://app', instances)
    return Client(url='http://app/api', session=Session(), debug=True)


@pytest.fixture
def fcl(filters):
    Session.register('http://app', filters)
    return Client(url='http://app/api', session=Session(), debug=True)
