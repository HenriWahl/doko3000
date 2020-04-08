import os
from pathlib import Path
basedir = Path(__file__).parent

class Config:
    # to be given by environment variable
    print('sqlite://' + str(basedir / 'doko3000.db'))
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dummykey'
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URL') or 'sqlite://' + str(basedir / 'doko3000.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = True
