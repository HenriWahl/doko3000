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

from doko3000 import app, \
    socketio
from doko3000.forms import Login
from doko3000.game import Deck, \
    game, \
    Player


@socketio.on('my event')
def handle_my_custom_event(json, methods=['GET', 'POST']):
    print(f'received event: {json}')
    socketio.emit('my response', json)


@socketio.on('who-am-i')
def who_am_i():
    print('who-am-i', current_user)
    if not current_user.is_anonymous:
        socketio.emit('you-are-what-you-is',
                      {'playername': current_user.name})


@socketio.on('new-table')
def new_table(msg):
    print('new_table', current_user)
    game.add_table('test2')
    game.tables['test2'].add_player(current_user.name)
    socketio.emit('new-table-available',
                  {'tables': game.get_tables_names(),
                   'playername': current_user.name,
                   'html': render_template('list_tables.html',
                                           tables=game.get_tables())},
                  broadcast=True)


@socketio.on('played-card')
def played_card(msg):
    print('played-card', current_user, msg['card_id'], msg['card_name'])
    card_id = msg['card_id']
    table = game.tables[msg['table']]
    if current_user.name == msg['playername'] == table.current_round.current_player.name:
        table.current_round.current_trick.add_turn(msg['playername'], card_id)
        table.current_round.turn_count += 1
        is_last_turn = table.current_round.current_trick.is_last_turn()
        next_player = table.current_round.get_next_player()
        socketio.emit('played-card-by-user',
                      {'playername': msg['playername'],
                       'card_id': card_id,
                       'card_name': msg['card_name'],
                       'is_last_turn': is_last_turn,
                       'next_player': next_player.name,
                       'html': {'card': render_template('card.html',
                                               card=Deck.cards[card_id],
                                               table=table),
                                'hud_players': render_template('hud_players.html',
                                                               order=table.current_round.order,
                                                               is_last_turn=is_last_turn,
                                                               next_player=next_player.name)
                                }},
                      broadcast=True)


@socketio.on('enter-table')
def enter_table(msg):
    print(msg)
    table = game.tables[msg['table']]
    playername = msg['playername']
    if table in game.tables:
        if playername not in game.tables[table].players:
            game.tables[table].add_player(playername)
            join_room(table.name)


@socketio.on('deal-cards')
def deal_cards(msg):
    table = game.tables[msg['table']]
    table.add_round()

    # just tell everybody to get personal cards
    socketio.emit('grab-your-cards',
                  {'table': table.name})


@socketio.on('my-cards-please')
def deal_cards_to_player(msg):
    playername = msg['playername']
    if playername == current_user.name and \
            msg['table'] in game.tables:
        print(msg)
        table = game.tables[msg['table']]
        if playername in table.current_round.players:
            cards = table.current_round.players[playername].cards
            socketio.emit('your-cards-please',
                          {'playername': playername,
                           'turn_count': table.current_round.turn_count,
                           'next_player': table.current_round.order[1].name,
                           # 'order_names': table.current_round.order_names,
                           'html': {'cards_hand': render_template('cards_hand.html',
                                                                  cards=cards,
                                                                  table=table),
                                    'hud_players': render_template('hud_players.html',
                                                                   order=table.current_round.order,
                                                                   next_player=table.current_round.order[1].name)}},
                          room=request.sid)


@socketio.on('claim-trick')
def claimed_trick(msg):
    playername = msg['playername']
    if playername == current_user.name and \
            msg['table'] in game.tables:
        print(msg)
        table = game.tables[msg['table']]
        if playername in table.current_round.players:
            if not table.current_round.is_finished():
                # when ownership changes it does at previous trick because normally there is a new one created
                # so the new one becomes the current one and the reclaimed is the previous
                if not len(table.current_round.current_trick) == 0:
                    # old trick, freshly claimed
                    table.current_round.current_trick.owner = table.current_round.players[playername]
                    # new trick for next turns
                    table.current_round.add_trick(table.players[playername])
                else:
                    # apparently the ownership of the previous trick is not clear - change it
                    table.current_round.previous_trick.owner = table.current_round.players[playername]
                    table.current_round.current_player = table.current_round.players[playername]
                socketio.emit('next-trick',
                              {'next_player': playername},
                              broadcast=True)
            else:
                table.current_round.current_trick.owner = table.current_round.players[playername]
                print('finished', table.current_round.turn_count, len(Deck.cards))
                print(table.current_round.tricks)
                print(table.current_round.get_score())
                # tell everybody stats and wait for everybody confirming next round
                socketio.emit('round-finished',
                              {'table': table.name,
                               'html': render_template('score.html',
                                                       table=table,
                                                       score=table.current_round.get_score())
                               },
                              broadcast=True)


@socketio.on('ready-for-next-round')
def ready_for_next_round(msg):
    playername = msg['playername']
    if playername == current_user.name and \
            msg['table'] in game.tables:
        print(msg)
        table = game.tables[msg['table']]
        table.add_ready_player(playername)
        if len(table.players_ready) == len(table.players):
            table.shift_players()
            table.add_round()
            table.reset_ready_players()
            # just tell everybody to get personal cards
            socketio.emit('start-next-round',
                          {'table': table.name,
                           'dealer': table.current_round.order[0].name})


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = Login()
    if form.validate_on_submit():
        player = Player.query.filter_by(name=form.playername.data).first()
        if player is None or not player.check_password(form.password.data):
            flash('Unknown user or wrong password :-(')
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


@app.route('/table/<table>')
@login_required
def table(table=''):
    if table in game.tables and \
            current_user.name in game.tables[table].players:
        print('user in table')
        return render_template('table.html',
                               title=f'doko3000 {table}',
                               table=game.tables[table],
                               dealer=game.tables[table].current_round.order[0].name
                               )
    return render_template('index.html',
                           tables=game.tables,
                           title='doko3000')
