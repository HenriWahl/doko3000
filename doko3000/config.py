import os
from pathlib import Path
basedir = Path(__file__).parent

class Config:
    # to be given by environment variable
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dummykey'
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI') or \
                                             'sqlite:///data/doko3000.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = True
