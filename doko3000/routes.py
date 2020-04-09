# routes for web interface part of doko3000
from functools import wraps
from threading import Event,\
                      Thread
import time

from flask import flash,\
                  redirect,\
                  render_template,\
                  request,\
                  url_for
from flask_login import current_user,\
                        login_required,\
                        login_user,\
                        logout_user
from flask_socketio import disconnect

from doko3000 import app,\
                     socketio
from doko3000.forms import Login
from doko3000.game import game
from doko3000.models import User


# to be set later by socketio.start_background_task()
message_thread = Thread()
message_thread_stopped = Event()

@socketio.on('my event')
def handle_my_custom_event(json, methods=['GET', 'POST']):
    print(f'received event: {json}')
    socketio.emit('my response', json)


@socketio.on('connect')
def connect():
    global message_thread
    print(current_user)
    if game.has_sessions():
        socketio.emit('session_available', {'data': 456})
        print(request.sid)
    else:
        socketio.emit('no session', None)

    if current_user.is_authenticated and not message_thread.is_alive():
        message_thread = socketio.start_background_task(message_processor)

@socketio.on('whoami')
def whoami():
    print(current_user)


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


def message_processor():
    while not message_thread_stopped.is_set():
        socketio.emit('thread_test', {'data': time.time()})
        print('emit')
        socketio.sleep(1)
