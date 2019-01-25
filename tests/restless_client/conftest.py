import time
import pytest
import flask_restless
from flask import Flask
from multiprocessing import Process
from flask_sqlalchemy import SQLAlchemy
from restless_client_server import DataModel


def create_webapp():
    app = Flask(__name__)
    
    db = SQLAlchemy(app)

    

    db.create_all()

    manager = flask_restless.APIManager(app, flask_sqlalchemy_db=db)
    manager.create_api(Person, methods=['GET'], include_columns=['name'])
    manager.create_api(Computer, methods=['GET'], collection_name='compjutahs', exclude_columns=['name'])
    data_model = DataModel(manager)
    manager.create_api(data_model, methods=['GET'])

    return app


@pytest.fixture(scope='function')
def runserver(request):
    def run():
        create_webapp().run()
    p = Process(target=run)
    p.start()

    def finalize():
        p.terminate()

    request.addfinalizer(finalize)
    time.sleep(0.1)

    yield p
