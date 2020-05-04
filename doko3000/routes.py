# routes for web interface part of doko3000

from flask import flash, \
    redirect, \
    render_template, \
    request, \
    url_for
from flask_login import current_user, \
    login_required, \
    login_user, \
    logout_user
from flask_socketio import join_room

from . import app, \
    login, \
    socketio
from .forms import Login
from .game import Deck, \
    game


@login.user_loader
def load_user(id):
    # return Player.query.get(int(id))
    return game.players[id]


@socketio.on('my event')
def handle_my_custom_event(json, methods=['GET', 'POST']):
    print(f'received event: {json}')
    socketio.emit('my response', json)


@socketio.on('who-am-i')
def who_am_i():
    print('who-am-i', current_user)
    if not current_user.is_anonymous:
        socketio.emit('you-are-what-you-is',
                      {'player_id': current_user.id})


@socketio.on('new-table')
def new_table(msg):
    print('new_table', current_user)
    game.add_table('test2')
    game.tables['test2'].add_player(current_user.id)
    socketio.emit('new-table-available',
                  {'tables': game.get_tables_names(),
                   'player_id': current_user.id,
                   'html': render_template('list_tables.html',
                                           tables=game.get_tables())},
                  broadcast=True)


@socketio.on('played-card')
def played_card(msg):
    print('played-card', current_user, msg['card_id'], msg['card_name'])
    card_id = msg['card_id']
    table = game.tables[msg['table']]
    if current_user.id == msg['player_id'] == table.round.current_player:
        table.round.current_trick.add_turn(msg['player_id'], card_id)
        table.round.increase_turn_count()
        is_last_turn = table.round.current_trick.is_last_turn()
        next_player = table.round.get_next_player()
        socketio.emit('played-card-by-user',
                      {'player_id': msg['player_id'],
                       'card_id': card_id,
                       'card_name': msg['card_name'],
                       'is_last_turn': is_last_turn,
                       'next_player': next_player,
                       'html': {'card': render_template('card.html',
                                               card=Deck.cards[card_id],
                                               table=table),
                                }},
                      broadcast=True)


@socketio.on('enter-table')
def enter_table(msg):
    print(msg)
    # table = game.tables[msg['table']]
    table = msg['table']
    player_id = msg['player_id']
    if table in game.tables:
        if player_id not in game.tables[table].players:
            game.tables[table].add_player(player_id)
        join_room(table)


@socketio.on('deal-cards')
def deal_cards(msg):
    table = game.tables[msg['table']]
    table.new_round()

    # just tell everybody to get personal cards
    socketio.emit('grab-your-cards',
                  {'table': table.id})


@socketio.on('my-cards-please')
def deal_cards_to_player(msg):
    player_id = msg['player_id']
    if player_id == current_user.id and \
            msg['table'] in game.tables:
        print(msg)
        table = game.tables[msg['table']]
        if player_id in table.round.players:
            # cards = table.round.players[player_id].cards
            cards = game.players[player_id].get_cards()
            # player = table.round.players[player_id]
            player = game.players[player_id]
            dealer = table.get_dealer()
            next_player = table.round.order[1]
            socketio.emit('your-cards-please',
                          {'player_id': player_id,
                           'turn_count': table.round.turn_count,
                           'next_player': table.round.order[1],
                           # 'order_names': table.round.order_names,
                           'html': {'cards_hand': render_template('cards_hand.html',
                                                                  cards=cards,
                                                                  table=table),
                                    'hud_players': render_template('hud_players.html',
                                                                   player=player,
                                                                   dealer=dealer,
                                                                   next_player=next_player)}},
                          room=request.sid)


@socketio.on('claim-trick')
def claimed_trick(msg):
    player_id = msg['player_id']
    if player_id == current_user.id and \
            msg['table'] in game.tables:
        print(msg)
        table = game.tables[msg['table']]
        if player_id in table.round.players:
            if not table.round.is_finished():
                # when ownership changes it does at previous trick because normally there is a new one created
                # so the new one becomes the current one and the reclaimed is the previous
                if not len(table.round.current_trick) == 0:
                    # old trick, freshly claimed
                    # table.round.current_trick.owner = table.round.players[player_id]
                    table.round.current_trick.owner = player_id
                    # new trick for next turns
                    # table.round.add_trick(table.players[player_id])
                    table.round.add_trick(player_id)
                else:
                    # apparently the ownership of the previous trick is not clear - change it
                    table.round.previous_trick.owner = player_id
                    table.round.current_player = player_id
                socketio.emit('next-trick',
                              {'next_player': player_id,
                               'score': table.round.get_score()},
                              broadcast=True)
            else:
                table.round.current_trick.owner = player_id
                print(table.round.tricks)
                print(table.round.get_score())
                # tell everybody stats and wait for everybody confirming next round
                socketio.emit('round-finished',
                              {'table': table.id,
                               'html': render_template('score.html',
                                                       table=table,
                                                       score=table.round.get_score())
                               },
                              broadcast=True)


@socketio.on('ready-for-next-round')
def ready_for_next_round(msg):
    player_id = msg['player_id']
    if player_id == current_user.id and \
            msg['table'] in game.tables:
        print(msg)
        table = game.tables[msg['table']]
        table.add_ready_player(player_id)
        if len(table.players_ready) == len(table.players):
            table.shift_players()
            dealer = table.get_dealer()
            table.reset_ready_players()
            # just tell everybody to get personal cards
            socketio.emit('start-next-round',
                          {'table': table.id,
                           'dealer': dealer})


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = Login()
    if form.validate_on_submit():
        if not form.player_id.data in game.players:
            flash('Unknown player :-(')
            return redirect(url_for('login'))
        else:
            player = game.players[form.player_id.data]
            if not player.check_password(form.password.data):
                flash('Wrong password :-(')
                return redirect(url_for('login'))
            login_user(player)
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
                           players=game.get_players(),
                           title='doko3000')


@app.route('/table/<table_id>')
@login_required
def table(table_id=''):
    if table_id in game.tables and \
            current_user.id in game.tables[table_id].players:
        print('user in table')
        return render_template('table.html',
                               title=f'doko3000 {table_id}',
                               table=game.tables[table_id],
                               dealer=game.tables[table_id].get_dealer()
                               )
    return render_template('index.html',
                           tables=game.tables,
                           title='doko3000')
