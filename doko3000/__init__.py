from flask import Flask,\
                  render_template,\
                  request
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

from doko3000.config import Config

# initialize app
app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
# extend by socket.io
socketio = SocketIO(app,
                    path='/doko3000')

# workaround from Miguel Grinberg - even if not PEP8-ic
from doko3000 import models,\
                     routes
