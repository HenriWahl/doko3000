# web interface part of doko3000
import time
from threading import Event,\
                      Thread

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

# to be set later by socketio.start_background_task()
message_thread = Thread()
message_thread_stopped = Event()

def message_processor():
    while not message_thread_stopped.is_set():
        socketio.emit('thread_test', {'data': time.time()})
        print('emit')
        socketio.sleep(1)


class Web:
    """
    bundles all web-related stuff
    """

    def __init__(self):
        @socketio.on('my event')
        def handle_my_custom_event(json, methods=['GET', 'POST']):
            print(f'received event: {json}')
            socketio.emit('my response', json)

        @socketio.on('connect')
        def connect():
            global message_thread
            if game.has_sessions():
                socketio.emit('session_available', {'data': 456})
                print(request.sid)
            else:
                socketio.emit('no session', None)
            if not message_thread.is_alive():
                message_thread = socketio.start_background_task(message_processor)

        @app.route('/')
        def index():
            return render_template('index.html')




