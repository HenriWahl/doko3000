from time import time

from flask import Flask
from flask_login import LoginManager
from flask_socketio import SocketIO

from .config import Config
from .database import DB

# initialize app
app = Flask(__name__)
app.config.from_object(Config)
app.jinja_env.globals.update(timestamp=int(time()))
# initialize database
db = DB(app)
# login
login = LoginManager(app)
login.login_view = 'login'
# extend by socket.io
socketio = SocketIO(app)

# workaround from Miguel Grinberg - even if not PEP8-ic
from doko3000 import game,\
                     routes
