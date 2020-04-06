# web interface part of doko3000

import json

from flask import Flask,\
                  render_template,\
                  request
from flask_socketio import SocketIO

from game import game

# initalize app
app = Flask(__name__)
# to be given by environment variable
app.config['SECRET_KEY'] = 'dummykey'
# extend by socket.io
socketio = SocketIO(app,
                    path='/doko3000')

# extend by socket.io
socketio = SocketIO(app,
                    path='/doko3000')

def message_received(methods=['GET', 'POST']):
    print('message received')

@socketio.on('my event')
def handle_my_custom_event(json, methods=['GET', 'POST']):
    print(f'received event: {json}')
    socketio.emit('my response', json, callback=message_received)

@socketio.on('connect')
def connect():
    if game.has_sessions():
        socketio.emit('session_available', {'data': 456})
        print(request.sid)
    else:
        socketio.emit('no session', None)

@app.route('/')
def index():
    return render_template('index.html')

