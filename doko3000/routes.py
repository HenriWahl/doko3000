# routes for web interface part of doko3000

from flask import flash, \
    redirect, \
    render_template, \
    request, \
    url_for
from flask_login import AnonymousUserMixin, \
    current_user, \
    login_required, \
    login_user, \
    logout_user
from flask_socketio import join_room

from doko3000 import app, \
    socketio
from doko3000.forms import Login
from doko3000.game import Deck,\
                          game
from doko3000.models import User


@socketio.on('my event')
def handle_my_custom_event(json, methods=['GET', 'POST']):
    print(f'received event: {json}')
    socketio.emit('my response', json)


@socketio.on('whoami')
def whoami():
    print('whoami', current_user)
    if not current_user.is_anonymous:
        socketio.emit('you-are-what-you-is',
                      {'username': current_user.username},
                      room=request.sid)


@socketio.on('new-table')
def new_table(msg):
    print('new_table', current_user)
    game.add_table('test2')
    game.tables['test2'].add_player(current_user.username)
    socketio.emit('new-table-available',
                  {'tables': game.get_tables_names(),
                   'username': current_user.username,
                   'html': render_template('list_tables.html',
                                           tables=game.get_tables())},
                   broadcast=True)


@socketio.on('played-card')
def played_card(msg):
    print('played-card', current_user, msg['card_id'], msg['card_name'])
    card_id = msg['card_id']
    table = game.tables[msg['table']]
    socketio.emit('played-card-by-user', {'username': msg['username'],
                                          'card_id': card_id,
                                          'card_name': msg['card_name'],
                                          'next_player': table.current_round.get_next_player().name,
                                          'html': render_template('card.html',
                                                                  card=Deck.cards[card_id],
                                                                  table=table)},
                  broadcast=True)


@socketio.on('enter-table')
def enter_table(msg):
    print(msg)
    table = game.tables[msg['table']]
    username = msg['username']
    if table in game.tables:
        if not username in game.tables[table].players:
            game.tables[table].add_player(username)


@socketio.on('deal-cards')
def deal_cards(msg):
    table = game.tables[msg['table']]
    table.add_round()
    # just tell everybody to get personal cards
    socketio.emit('grab-your-cards', {'table': table.name})


@socketio.on('my-cards-please')
def deal_cards_to_player(msg):
    username = msg['username']
    if username == current_user.username and \
            msg['table'] in game.tables:
        print(msg)
        table = game.tables[msg['table']]
        if username in table.current_round.players:
            cards = table.current_round.players[username].cards
            socketio.emit('your-cards-please', {'username': username,
                                                'next_player': table.current_round.order[1].name,
                                                'html': render_template('cards_hand.html',
                                                                        cards=cards,
                                                                        table=table)},
                          room=request.sid)


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
                           tables=game.get_tables(),
                           title='doko3000')


@app.route('/table/<table>')
@login_required
def table(table=''):
    if table in game.tables and \
            current_user.username in game.tables[table].players:
        print('user in table')
        return render_template('table.html',
                               title=f'doko3000 {table}',
                               table=game.tables[table])
    return render_template('index.html',
                           tables=game.tables,
                           title='doko3000')
