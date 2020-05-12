import os
from pathlib import Path

basedir = Path(__file__).parent


class Config:
    # to be given by environment variable
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dummykey'
    # # database
    # SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI') or \
    #                           'sqlite:///data/doko3000.db'
    # SQLALCHEMY_TRACK_MODIFICATIONS = True
    # # session handling
    # SESSION_TYPE = 'sqlalchemy'
    # CouchDB, according to https://hub.docker.com/_/couchdb
    COUCHDB_URL = os.environ.get('COUCHDB_URL') or 'http://couchdb:5984'
    COUCHDB_DATABASE = os.environ.get('COUCHDB_DATABASE') or 'doko3000'
    COUCHDB_USER = os.environ.get('COUCHDB_USER') or 'admin'
    COUCHDB_PASSWORD = os.environ.get('COUCHDB_PASSWORD') or 'doko3000'


class DummyApp:
    def __init__(self):
        self.config = Config.__dict__
