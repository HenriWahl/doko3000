from time import time

from flask import flash, \
    Flask, \
    jsonify, \
    redirect, \
    render_template, \
    request, \
    url_for
from flask_login import current_user, \
    LoginManager, \
    login_required, \
    login_user, \
    logout_user
from flask_socketio import join_room, \
    SocketIO

from .config import Config
from .database import DB
from .game import Deck, \
    Game
from .misc import is_xhr, \
    Login

# initialize app
app = Flask(__name__)
app.config.from_object(Config)
# timestamp for files which may change during debugging like .js and .css
app.jinja_env.globals.update(timestamp=int(time()))
# initialize database
db = DB(app)
# login
login = LoginManager(app)
login.login_view = 'login'
# empty message avoids useless errorflash-messae-by-default
login.login_message = ''
# extend by socket.io
socketio = SocketIO(app, manage_session=False)

game = Game(db)
game.load_from_db()


@login.user_loader
def load_user(id):
    """
    give user back if it exists, otherwise force login
    """
    try:
        player = game.players[id]
        return player
    except KeyError:
        return None


@socketio.on('who-am-i')
def who_am_i():
    if not current_user.is_anonymous:
        player = game.players.get(current_user.get_id())
        if player:
            table = game.tables.get(player.table)
            round_finished = False
            # if player already sits on a table inform client
            if table:
                current_player_id = table.round.current_player
                round_finished = table.round.is_finished()
                join_room(table.id)
            else:
                current_player_id = ''
            socketio.emit('you-are-what-you-is',
                          {'player_id': player.id,
                           'table_id': table.id,
                           'current_player_id': current_player_id,
                           'round_finished': round_finished})


@socketio.on('played-card')
def played_card(msg):
    card_id = msg.get('card_id')
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    if card_id in Deck.cards and \
       player and \
       table and \
       player.table == table.id and \
       current_user.get_id() == player.id == table.round.current_player:
        table.round.current_trick.add_turn(player.id, card_id)
        table.round.increase_turn_count()
        card = Deck.cards[card_id]
        player.remove_card(card.id)
        is_last_turn = table.round.current_trick.is_last_turn()
        current_player_id = table.round.get_current_player()
        idle_players = table.idle_players
        cards_table = table.round.current_trick.get_cards()
        played_cards = table.round.get_played_cards()
        timestamp = table.round.timestamp
        socketio.emit('played-card-by-user',
                      {'player_id': player.id,
                       'card_id': card.id,
                       'card_name': card.name,
                       'is_last_turn': is_last_turn,
                       'current_player_id': current_player_id,
                       'idle_players': idle_players,
                       'played_cards': played_cards,
                       'html': {'cards_table': render_template('cards/table.html',
                                                               cards_table=cards_table,
                                                               table=table,
                                                               timestamp=timestamp),
                                'hud_players': render_template('top/hud_players.html',
                                                               table=table,
                                                               player=player,
                                                               current_player_id=current_player_id)
                                }},
                      room=table.id)


@socketio.on('enter-table')
def enter_table_socket(msg):
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    if player and table:
        if (table.locked and player.id in table.players) or \
                not table.locked:
            game.tables[table.id].add_player(player.id)
            join_room(table.id)
            # check if any formerly locked table is now emtpy and should be unlocked
            game.check_tables()


@socketio.on('setup-table-change')
def setup_table(msg):
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    action = msg.get('action')
    if player and table:
        if action == 'remove_player':
            table.remove_player(player.id)
        elif action == 'lock_table':
            table.locked = True
        elif action == 'unlock_table':
            table.locked = False
        elif action == 'play_with_9':
            table.round.with_9 = True
        elif action == 'play_without_9':
            table.round.with_9 = False
        elif action == 'allow_undo':
            table.round.allow_undo = True
        elif action == 'prohibit_undo':
            table.round.allow_undo = False
        elif action == 'changed_order':
            order = msg.get('order')
            if set(order) == set(table.order):
                table.players = order
        elif action == 'start_table':
            table.start()
            # just tell everybody to get personal cards
            socketio.emit('grab-your-cards',
                          {'table_id': table.id},
                          room=table.id)


@socketio.on('setup-player-change')
def setup_player(msg):
    action = msg.get('action')
    player = game.players.get(msg.get('player_id'))
    if player:
        if action == 'is_admin':
            player.is_admin = True
        elif action == 'is_no_admin':
            player.is_admin = False
        elif action == 'allows_spectators':
            player.allows_spectators = True
        elif action == 'denies_spectators':
            player.allows_spectators = False
        elif action == 'new_password':
            password = msg.get('password')
            if password:
                player.set_password(password)
                socketio.emit('change-password-successful',
                              {'player_id': player.id},
                              room=request.sid)
            else:
                socketio.emit('change-password-failed',
                              {'player_id': player.id},
                              room=request.sid)


@socketio.on('deal-cards')
def deal_cards(msg):
    table = game.tables.get(msg.get('table_id'))
    if table:
        table.reset_round()
        # just tell everybody to get personal cards
        socketio.emit('grab-your-cards',
                      {'table_id': table.id},
                      room=table.id)


@socketio.on('deal-cards-again')
def deal_cards_again(msg):
    table = game.tables.get(msg.get('table_id'))
    if table:
        # ask dealer if really should be re-dealt
        socketio.emit('really-deal-again',
                      {'table_id': table.id,
                       'html': render_template('round/request_deal_again.html',
                                               table=table)},
                      room=request.sid)


@socketio.on('my-cards-please')
def deal_cards_to_player(msg):
    """
    give player cards after requesting them
    """
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    if player and \
       table and \
       player.table == table.id and \
       player.id == current_user.get_id() and \
       player.id in table.players:
        dealer = table.dealer
        # just in case
        join_room(table.id)
        current_player_id = table.round.current_player
        timestamp = table.round.timestamp
        if player.id in table.round.players:
            cards_hand = player.get_cards()
            cards_table = []
            # no score yet but needed for full set of cards for hand - to decide if back-card is shown too
            score = table.round.get_score()
            mode = 'player'
            dealing_needed = table.round.turn_count == 0
            # if one trick right now was finished the claim-trick-button should be displayed again
            trick_claiming_needed = table.round.turn_count % 4 == 0 and \
                                    table.round.turn_count > 0 and \
                                    not table.round.is_finished()
            socketio.emit('your-cards-please',
                          {'player_id': player.id,
                           'turn_count': table.round.turn_count,
                           'current_player_id': current_player_id,
                           'dealer': dealer,
                           'dealing_needed': dealing_needed,
                           'trick_claiming_needed': trick_claiming_needed,
                           'html': {'cards_hand': render_template('cards/hand.html',
                                                                  cards_hand=cards_hand,
                                                                  table=table,
                                                                  player=player,
                                                                  score=score,
                                                                  timestamp=timestamp),
                                    'hud_players': render_template('top/hud_players.html',
                                                                   table=table,
                                                                   player=player,
                                                                   dealer=dealer,
                                                                   current_player_id=current_player_id),
                                    'cards_table': render_template('cards/table.html',
                                                                   cards_table=cards_table,
                                                                   table=table,
                                                                   timestamp=timestamp,
                                                                   mode=mode)}
                           },
                          room=request.sid)
        else:
            # spectator mode
            players = table.round.players
            players_cards = table.round.get_players_cards()
            cards_table = table.round.current_trick.get_cards()
            mode = 'spectator'
            socketio.emit('sorry-no-cards-for-you',
                          {'html': {'hud_players': render_template('top/hud_players.html',
                                                                   table=table,
                                                                   player=player,
                                                                   dealer=dealer,
                                                                   current_player_id=current_player_id),
                                    'cards_table': render_template('cards/table.html',
                                                                   cards_table=cards_table,
                                                                   table=table,
                                                                   timestamp=timestamp,
                                                                   mode=mode),
                                    'cards_hand_spectator_upper': render_template('cards/hand_spectator_upper.html',
                                                                                 table=table,
                                                                                 players=players,
                                                                                 players_cards=players_cards),
                                    'cards_hand_spectator_lower': render_template('cards/hand_spectator_lower.html',
                                        table=table,
                                        players=players,
                                        players_cards=players_cards)
                                    }},
                          room=request.sid)


@socketio.on('sorted-cards')
def sorted_cards(msg):
    """
    while player sorts cards every card placed somewhere causes transmission of current card sort order
    which gets saved here
    """
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    if player and table:
        if player.id == current_user.get_id() and \
           player.id in game.players and \
           player.table == table.id:
                cards_hand_ids = msg.get('cards_hand_ids')
                if set(cards_hand_ids) == set(player.cards):
                    player.cards = cards_hand_ids
                    player.save()


@socketio.on('claim-trick')
def claimed_trick(msg):
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    if player and \
       table and \
       player.id == current_user.get_id():
        if player.id in table.round.players:
            if not table.round.is_finished():
                # when ownership changes it does at previous trick because normally there is a new one created
                # so the new one becomes the current one and the reclaimed is the previous
                if not len(table.round.current_trick.cards) == 0:
                    # old trick, freshly claimed
                    # table.round.current_trick.owner = table.round.players[player_id]
                    table.round.current_trick.owner = player.id
                    # new trick for next turns
                    table.round.add_trick(player.id)
                else:
                    # apparently the ownership of the previous trick is not clear - change it
                    table.round.previous_trick.owner = player.id
                    table.round.current_player = player.id
                score = table.round.get_score()
                timestamp = table.round.timestamp
                cards_table = []
                table.round.calculate_trick_order()
                socketio.emit('next-trick',
                              {'current_player_id': player.id,
                               'score': score,
                               'html': {'hud_players': render_template('top/hud_players.html',
                                                                       table=table,
                                                                       player=player,
                                                                       current_player_id=player.id),
                                        'cards_table': render_template('cards/table.html',
                                                                       cards_table=cards_table,
                                                                       table=table,
                                                                       timestamp=timestamp)
                                        }},
                              room=table.id)
            else:
                table.round.current_trick.owner = player.id
                players = game.players
                score = table.round.get_score()
                table.shift_players()
                # tell everybody stats and wait for everybody confirming next round
                socketio.emit('round-finished',
                              {'table_id': table.id,
                               'html': render_template('round/score.html',
                                                       table=table,
                                                       players=players,
                                                       score=score)
                               },
                              room=table.id)


@socketio.on('need-final-result')
def send_final_result(msg):
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    if player and \
       table and \
       player.id == current_user.get_id() and \
       player.table == table.id:
        players = game.players
        score = table.round.get_score()
        # tell single player stats and wait for everybody confirming next round
        socketio.emit('round-finished',
                      {'table_id': table.id,
                       'html': render_template('round/score.html',
                                               table=table,
                                               players=players,
                                               score=score)
                       },
                      room=request.sid)


@socketio.on('ready-for-next-round')
def ready_for_next_round(msg):
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    if player and \
       table and \
       player.id == current_user.get_id():
        table.add_ready_player(player.id)
        game.players[player.id].remove_all_cards()
        dealer = table.dealer
        next_players = table.order[:4]
        number_of_rows = max(len(next_players), len(table.idle_players))
        if set(table.players_ready) >= set(table.round.players):
            # now shifted when round is finished
            # table.shift_players()
            table.reset_ready_players()
            # just tell everybody to get personal cards
        socketio.emit('start-next-round',
                      {'table_id': table.id,
                       'dealer': dealer,
                       'html': render_template('round/info.html',
                                               table=table,
                                               dealer=dealer,
                                               next_players=next_players,
                                               number_of_rows=number_of_rows)
                       },
                      room=request.sid)


@socketio.on('request-round-finish')
def request_round_finish(msg):
    table = game.tables.get(msg.get('table_id'))
    if table:
        # clear list of ready players for next poll
        table.reset_ready_players()
        # just tell everybody to get personal cards
        socketio.emit('round-finish-requested',
                      {'table_id': table.id,
                       'html': render_template('round/request_finish.html',
                                               table=table)
                       },
                      room=table.id)


@socketio.on('ready-for-round-finish')
def round_finish(msg):
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    if player and \
       table and \
       player.id == current_user.get_id():
        table.add_ready_player(player.id)
        if set(table.players_ready) >= set(table.round.players):
            table.shift_players()
            dealer = table.dealer
            table.reset_ready_players()
            next_players = table.order[:4]
            number_of_rows = max(len(next_players), len(table.idle_players))
            # just tell everybody to get personal cards
            socketio.emit('start-next-round',
                          {'table_id': table.id,
                           'dealer': dealer,
                           'html': render_template('round/info.html',
                                                   table=table,
                                                   next_players=next_players,
                                                   number_of_rows=number_of_rows)},
                          room=table.id)


@socketio.on('request-round-reset')
def request_round_reset(msg):
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    if player and \
       table and \
       player.id in table.players:
        # clear list of ready players for next poll
        table.reset_ready_players()
        # just tell everybody to get personal cards
        socketio.emit('round-reset-requested',
                      {'table_id': table.id,
                       'html': render_template('round/request_reset.html',
                                               table=table)
                       },
                      room=table.id)


@socketio.on('ready-for-round-reset')
def round_reset(msg):
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    if player and \
       table and \
       player.id == current_user.get_id():
        table.add_ready_player(player.id)
        if set(table.players_ready) >= set(table.round.players):
            table.reset_round()
            socketio.emit('grab-your-cards',
                          {'table_id': table.id},
                          room=table.id)


@socketio.on('request-undo')
def request_undo(msg):
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    if player and \
       table and \
       player.id in table.players:
        # makes only sense if there was any card played yet
        if table.round.turn_count > 0:
            # clear list of ready players for next poll
            table.reset_ready_players()
            # just tell everybody that an undo was requested
            socketio.emit('undo-requested',
                          {'table_id': table.id,
                           'html': render_template('round/request_undo.html',
                                                   table=table)
                           },
                          room=table.id)


@socketio.on('ready-for-undo')
def round_reset(msg):
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    if player and \
       table and \
       player.id == current_user.get_id():
        table.add_ready_player(player.id)
        if set(table.players_ready) >= set(table.round.players):
            table.round.undo()
            socketio.emit('grab-your-cards',
                          {'table_id': table.id},
                          room=table.id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = Login()
    if form.validate_on_submit():
        if not form.player_id.data in game.players:
            flash('Spieler nicht bekannt :-(')
            return redirect(url_for('login'))
        else:
            player_id = game.players[form.player_id.data]
            if not player_id.check_password(form.password.data):
                flash('Falsches Passwort :-(')
                return redirect(url_for('login'))
            login_user(player_id)
            return redirect(url_for('index'))
    return render_template('login.html',
                           title=f"{app.config['TITLE']} Login",
                           form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    players = game.players.values()
    tables = game.tables.values()
    player = game.players.get(current_user.id)
    if player:
        return render_template('index.html',
                               tables=tables,
                               players=players,
                               player=player,
                               title=f"{app.config['TITLE']}")
    else:
        return redirect(url_for('login'))


@app.route('/table/<table_id>')
@login_required
def table(table_id=''):
    player = game.players.get(current_user.get_id())
    table = game.tables.get(table_id)
    if player and \
       table and \
       player.id in table.players:
        if player.id in table.round.players:
            dealer = table.dealer
            # if no card is played already the dealer might deal
            dealing_needed = table.round.turn_count == 0
            # if one trick right now was finished the claim-trick-button should be displayed again
            trick_claiming_needed = table.round.turn_count % 4 == 0 and \
                                    table.round.turn_count > 0 and \
                                    not table.round.is_finished()
            current_player_id = table.round.current_player
            cards_hand = player.get_cards()
            cards_table = table.round.current_trick.get_cards()
            timestamp = table.round.timestamp
            score = table.round.get_score()
            mode = 'player'
            return render_template('table.html',
                                   title=f"{app.config['TITLE']} {table_id}",
                                   table=table,
                                   dealer=dealer,
                                   dealing_needed=dealing_needed,
                                   trick_claiming_needed=trick_claiming_needed,
                                   player=player,
                                   current_player_id=current_player_id,
                                   cards_hand=cards_hand,
                                   cards_table=cards_table,
                                   timestamp=timestamp,
                                   score=score,
                                   mode=mode)
        else:
            players = table.round.players
            players_cards = table.round.get_players_cards()
            cards_table = table.round.current_trick.get_cards()
            mode = 'spectator'
            return render_template('table.html',
                                   title=f"{app.config['TITLE']} {table_id}",
                                   table=table,
                                   cards_table=cards_table,
                                   player=player,
                                   players=players,
                                   players_cards=players_cards,
                                   mode=mode)
    tables = game.tables.values()
    players = game.players.values()
    return render_template('index.html',
                           tables=tables,
                           players=players,
                           player=player,
                           title=f"{app.config['TITLE']}")


@app.route('/setup/table/<table_id>')
@login_required
def setup_table(table_id):
    """
    configure table, its players and start - should be no socket but xhr here for easier formular check
    well, formular check seems to be unnecessary for now, but anyway it is an easy way to deliver it
    """
    if is_xhr(request) and table_id:
        table = game.tables.get(table_id)
        if table and \
           current_user.get_id() in game.players and \
           (current_user.get_id() in table.players or
           not table.locked):
            return jsonify({'allowed': True,
                                'html': render_template('setup/table.html',
                                                        table=table)})
        else:
            return jsonify({'allowed': False})
    else:
        return redirect(url_for('index'))


@app.route('/setup/player/<player_id>')
@login_required
def setup_player(player_id):
    """
    Setup for player - at first only password, quite probably
    """
    if is_xhr(request) and player_id:
        player = game.players.get(player_id)
        if player:
            return jsonify({'html': render_template('setup/player.html',
                                                    player=player)})
        else:
            return redirect(url_for('index'))
    else:
        return redirect(url_for('index'))


@app.route('/enter/table/<table_id>/<player_id>')
@login_required
def enter_table_json(table_id='', player_id=''):
    """
    give #buttom_enter_table permission or not, depending on player membership or table lockedness
    support for socket.io request, just telling #button_enter_table if its link can be followed or not
    """
    if is_xhr(request) and table_id:
        allowed = False
        player = game.players.get(player_id)
        table = game.tables.get(table_id)
        if player and \
           table and \
           ((table.locked and player_id in table.players) or
           not table.locked):
            allowed = True
        return jsonify({'allowed': allowed})
    else:
        return redirect(url_for('index'))


@app.route('/get/tables')
@login_required
def get_html_tables():
    """
    get HTML list of tables to refresh index.html tables list after changes
    """
    if is_xhr(request):
        tables = game.tables.values()
        return jsonify({'html': render_template('index/list_tables.html',
                                                tables=tables)})
    else:
        return redirect(url_for('index'))


@app.route('/get/players')
@login_required
def get_html_players():
    """
    get HTML list of players to refresh index.html players list after changes
    """
    if is_xhr(request):
        players = game.players.values()
        return jsonify({'html': render_template('index/list_players.html',
                                                players=players)})
    else:
        return redirect(url_for('index'))


@app.route('/get/wait')
@login_required
def get_wait():
    """
    get HTML snippet asking for patience
    """
    if is_xhr(request):
        return jsonify({'html': render_template('round/wait.html')})
    else:
        return redirect(url_for('index'))


@app.route('/create/table', methods=['GET', 'POST'])
@login_required
def create_table():
    """
    create table via button
    """
    if is_xhr(request):
        if request.method == 'GET':
            return jsonify({'html': render_template('index/create_table.html')})
        elif request.method == 'POST':
            new_table_id = request.values.get('new_table_id')
            if new_table_id:
                if new_table_id in game.tables:
                    return jsonify({'status': 'error',
                                    'message': 'Diesen Tisch gibt es schon :-('})
                else:
                    game.add_table(new_table_id)
                    return jsonify({'status': 'ok'})
            else:
                return jsonify({'status': 'error',
                                'message': 'Der Tisch braucht einen Namen'})
        else:
            return redirect(url_for('index'))
    else:
        return redirect(url_for('index'))


@app.route('/create/player', methods=['GET', 'POST'])
@login_required
def create_player():
    """
    create table via button
    """
    if is_xhr(request) and current_user.is_admin:
        if request.method == 'GET':
            return jsonify({'html': render_template('index/create_player.html')})
        elif request.method == 'POST':
            new_player_id = request.values.get('new_player_id')
            new_player_password = request.values.get('new_player_password')
            if new_player_id:
                if new_player_id in game.players:
                    return jsonify({'status': 'error',
                                    'message': 'Diesen Spieler gibt es schon :-('})
                else:
                    if new_player_password:
                        player = game.add_player(player_id=new_player_id, password=new_player_password)
                        # player.set_password(new_player_password)
                        return jsonify({'status': 'ok'})
                    else:
                        return jsonify({'status': 'error',
                                        'message': 'Der Spieler braucht eine Passwort'})
            else:
                return jsonify({'status': 'error',
                                'message': 'Der Spieler braucht einen Namen'})
        else:
            return redirect(url_for('index'))
    else:
        return redirect(url_for('index'))


@app.route('/delete/player/<player_id>', methods=['GET', 'POST'])
@login_required
def delete_player(player_id):
    """
    delete player from players list on index page and thus from game at all
    """
    player = game.players.get(player_id)
    if is_xhr(request) and \
            player and \
            current_user.is_admin:
        if request.method == 'GET':
            if not player.is_playing():
                return jsonify({'status': 'ok',
                                'html': render_template('index/delete_player.html',
                                                        player=player)})
            else:
                return jsonify({'status': 'error',
                                'html': render_template('error.html',
                                                         message=f"{player.id} sitzt noch am Tisch {player.table}.")})
        elif request.method == 'POST':
            if game.delete_player(player.id):
                players = game.players.values()
                return jsonify({'status': 'ok',
                                'html': render_template('index/list_players.html',
                                                        players=players)})
    # default return if nothing applies
    return redirect(url_for('index'))


@app.route('/delete/table/<table_id>', methods=['GET', 'POST'])
@login_required
def delete_table(table_id):
    """
    delete table from players list on index page and thus from game at all
    """
    table = game.tables.get(table_id)
    if is_xhr(request) and \
            table:
        if request.method == 'GET':
            if len(table.players) == 0:
                return jsonify({'status': 'ok',
                                'html': render_template('index/delete_table.html',
                                                        table=table)})
            else:
                return jsonify({'status': 'error',
                                'html': render_template('error.html',
                                                         message=f"Es sitzen noch Spieler am Tisch {table.id}.")})
        elif request.method == 'POST':
            if game.delete_table(table.id):
                tables = game.tables.values()
                return jsonify({'status': 'ok',
                                'html': render_template('index/list_tables.html',
                                                        tables=tables)})
    # default return if nothing applies
    return redirect(url_for('index'))

@app.route('/start/table/<table_id>')
@login_required
def start_table(table_id):
    """
    start table after setting it up - ask first
    """
    table = game.tables.get(table_id)
    if is_xhr(request) and \
            table:
        if len(table.players) >= 4:
            return jsonify({'status': 'ok',
                            'html': render_template('index/start_table.html',
                                                    table=table)})
        else:
            return jsonify({'status': 'error',
                            'html': render_template('error.html',
                                                     message=f"Es sitzen nicht genug Spieler am Tisch {table.id}.")})
    else:
        return redirect(url_for('index'))
