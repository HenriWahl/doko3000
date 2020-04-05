#!/usr/bin/env python3
#
# ©2020 Henri Wahl
#
# Attempt to play good ol' Doppelkopf online
#

from pathlib import Path

from flask import Flask,\
                  render_template,\
                  send_file
from flask_bootstrap import Bootstrap
from flask_socketio import SocketIO

from game import test_session

# initalize app
app = Flask(__name__)
# to be given by environment variable
app.config['SECRET_KEY'] = 'dummykey'
# Bootstrap from Bootstrap-Flask
Bootstrap(app)
# extend by socket.io
socketio = SocketIO(app,
                    path='/doko3000')

# favicon.ico
FAVICON = Path(app.root_path, 'static', 'favicon.ico')


@app.route('/')
def sessions():
    return render_template('session.html')


def message_received(methods=['GET', 'POST']):
    print('message received')


@socketio.on('my event')
def handle_my_custom_event(json, methods=['GET', 'POST']):
    print(f'received event: {json}')
    socketio.emit('my response', json, callback=message_received)


@app.route('/favicon.ico')
def favicon():
    return send_file(FAVICON,
                     mimetype='image/vnd.microsoft.icon')

test_session()

if __name__ == '__main__':
    socketio.run(app,
                 host='::',
                 debug=True)
