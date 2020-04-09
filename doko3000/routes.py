# routes for web interface part of doko3000
from queue import Queue
from threading import Event, \
    Thread
import time

from flask import flash, \
    redirect, \
    render_template, \
    request, \
    url_for
from flask_login import current_user, \
    login_required, \
    login_user, \
    logout_user
from flask_socketio import emit

from doko3000 import app, \
                     socketio
from doko3000.forms import Login
from doko3000.game import game
from doko3000.models import BroadcastMessage, \
    User

# everything needed for a broadcast mechanism
broadcast_thread = Thread()
broadcast_thread_stopped = Event()
broadcast_queue = Queue()


@socketio.on('my event')
def handle_my_custom_event(json, methods=['GET', 'POST']):
    print(f'received event: {json}')
    socketio.emit('my response', json)


@socketio.on('connect')
def connect():
    global broadcast_queue, broadcast_thread
    print(current_user)
    if game.has_sessions():
        socketio.emit('session_available', {'data': 456})
        print(request.sid)
    else:
        socketio.emit('no session', None)

    # if current_user.is_authenticated and not broadcast_thread.is_alive():
    #     broadcast_thread = socketio.start_background_task(broadcast_sender, broadcast_queue)


@socketio.on('whoami')
def whoami():
    print('whoami', current_user)
    socketio.emit('you-are-what-you-is', {'username': current_user.username})


@socketio.on('button-pressed')
def button_pressed(data):
    print('testbutton', current_user)
    # broadcast_queue.put(BroadcastMessage('testbutton', {'username': current_user.username}))
    emit('button-pressed-by-user', {'username': current_user.username}, broadcast=True )

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = Login()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Unknown user or wrong password :-(')
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('index'))

    print(current_user, current_user.is_authenticated)

    return render_template('login.html',
                           title='doko3000 Login',
                           form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    return render_template('index.html',
                           title='doko3000')


def broadcast_sender(broadcast_queue):
    # while not broadcast_thread_stopped.is_set():
    while True:
        message = broadcast_queue.get()
        print(message)
        socketio.emit(message.name, message.content)
    print('what?')
