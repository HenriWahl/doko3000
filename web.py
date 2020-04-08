# web interface part of doko3000
import time
from threading import Event,\
                      Thread

from flask import Flask,\
                  render_template,\
                  request
from flask_socketio import SocketIO

from config import Config
from game import game

# initalize app
app = Flask(__name__)
# to be given by environment variable
#app.config['SECRET_KEY'] = 'dummykey'
app.config.from_object(Config)
# extend by socket.io
socketio = SocketIO(app,
                    path='/doko3000')

class Web:
    """
    bundles all web-related stuff
    """
    def __init__(self):
        # to be set later by socketio.start_background_task()
        self.message_thread = Thread()
        self.message_thread_stopped = Event()

        @socketio.on('my event')
        def handle_my_custom_event(json, methods=['GET', 'POST']):
            print(f'received event: {json}')
            socketio.emit('my response', json)

        @socketio.on('connect')
        def connect():
            if game.has_sessions():
                socketio.emit('session_available', {'data': 456})
                print(request.sid)
            else:
                socketio.emit('no session', None)
            if not self.message_thread.is_alive():
                self.message_thread = socketio.start_background_task(self.message_processor)

        @app.route('/')
        def index():
            return render_template('index.html')

    def message_processor(self):
        while not self.message_thread_stopped.is_set():
            socketio.emit('thread_test', {'data': time.time()})
            print('emit')
            socketio.sleep(1)

web = Web()

