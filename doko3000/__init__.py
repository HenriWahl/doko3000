from time import time
from urllib.parse import quote

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
# empty message avoids useless errorflash-message-by-default
login.login_message = ''
# extend by socket.io
# shorter ping interval for better sync
socketio = SocketIO(app,
                    manage_session=False,
                    # ping_timeout=2,
                    # # seems to be better somewhat higher for clients not getting nervous when waiting for reset
                    ping_timeout=15,
                    ping_interval=2,
                    # logger=True,
                    # engineio_logger=True,
                    # allow_upgrades=False,
                    cors_allowed_origins=Config.CORS_ALLOWED_ORIGINS)

# load game data from database after initialization
game = Game(db)
game.load_from_db()

# keep track of players and their sessions to enable directly emitting a socketio event
sessions = {}


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


# no decorator possible for socketio.on-events so make this a function
def check_message(msg, player_in_round=True, player_at_table=True):
    """
    check if message is correctly sent from player
    tries to avoid permanently repeated code

    player_in_round is important if there are more than 4 players - the fifth is at taböle but not in round
    player_at_table is a condition when player not yet belongs to table
    """
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    if player_in_round:
        if player and \
                table and \
                player.id in table.round.players and \
                player.id == current_user.id and \
                player.table == table.id:
            return True, player, table
        else:
            return False, player, table
    elif player_at_table:
        if player and \
                table and \
                player.id == current_user.id and \
                player.table == table.id:
            return True, player, table
        else:
            return False, player, table
    else:
        if player and \
                table and \
                player.id == current_user.id:
            return True, player, table
        else:
            return False, player, table


#
# ------------ Socket.io events ------------
#
@socketio.on('who-am-i')
def who_am_i():
    if not current_user.is_anonymous:
        player = game.players.get(current_user.get_id())
        if player:
            table = game.tables.get(player.table)
            round_finished = False
            round_reset = False
            # store player session for later usage
            sessions[player.id] = request.sid
            # if player already sits on a table inform client
            if table:
                current_player_id = table.round.current_player
                round_finished = table.round.is_finished()
                round_reset = table.round.is_reset()
                join_room(table.id)
                table_id = table.id
                sync_count = table.sync_count
            else:
                current_player_id = ''
                table_id = ''
                sync_count = 0
            # putting into variables makes debugging easier
            event = 'you-are-what-you-is'
            payload = {'player_id': player.id,
                       'table_id': table_id,
                       'sync_count': sync_count,
                       'current_player_id': current_player_id,
                       'round_finished': round_finished,
                       'round_reset': round_reset}
            room = request.sid
            # debugging...
            if table and table.is_debugging:
                table.log(event, payload, room)
            # ...and action
            socketio.emit(event, payload, room=room)


@socketio.on('enter-table')
def enter_table_socket(msg):
    msg_ok, player, table = check_message(msg, player_in_round=False, player_at_table=False)
    if msg_ok:
        if (table.locked and player.id in table.players) or \
                not table.locked:
            game.tables[table.id].add_player(player.id)
            join_room(table.id)
            # check if any formerly locked table is now emtpy and should be unlocked
            game.check_tables()
            socketio.emit('index-list-changed',
                          {'table': 'tables'})


@socketio.on('card-played')
def played_card(msg):
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        card_id = msg.get('card_id')
        if card_id in Deck.cards and \
                len(table.round.current_trick.cards) < 4 and \
                current_user.get_id() == player.id == table.round.current_player:
            table.round.current_trick.add_turn(player.id, card_id)
            table.round.increase_turn_count()
            card = Deck.cards[card_id]
            player.remove_card(card.id)
            is_last_turn = table.round.current_trick.is_last_turn()
            current_player_id = table.round.get_current_player_id()
            idle_players = table.idle_players
            if table.round.cards_shown:
                # cards_shown contains cqrds-showing player_id
                cards_table = game.players[table.round.cards_shown].get_cards()
            else:
                cards_table = table.round.current_trick.get_cards()
            played_cards = table.round.get_played_cards()
            cards_timestamp = table.round.cards_timestamp
            cards_shown = table.round.cards_shown
            sync_count = table.increase_sync_count()
            event = 'card-played-by-user',
            payload = {'player_id': player.id,
                       'table_id': table.id,
                       'card_id': card.id,
                       'card_name': card.name,
                       'is_last_turn': is_last_turn,
                       'current_player_id': current_player_id,
                       'idle_players': idle_players,
                       'players_spectator': table.players_spectator,
                       'played_cards': played_cards,
                       'cards_shown': cards_shown,
                       'sync_count': sync_count,
                       'html': {'cards_table': render_template('cards/table.html',
                                                               cards_table=cards_table,
                                                               table=table,
                                                               cards_timestamp=cards_timestamp),
                                'hud_players': render_template('top/hud_players.html',
                                                               table=table,
                                                               player=player,
                                                               game=game,
                                                               current_player_id=current_player_id)
                                }}
            room = table.id
            # debugging...
            if table.is_debugging:
                table.log(event, payload, room)
            # ...and action
            socketio.emit(event, payload, room=room)


@socketio.on('card-exchanged')
def card_exchanged(msg):
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        if table.round.exchange and \
                player.party in table.round.exchange:
            cards_table_ids = msg.get('cards_table_ids')
            table.round.update_exchange(player.id, cards_table_ids)


@socketio.on('exchange-player-cards-to-server')
def exchange_player_cards(msg):
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        if table.round.exchange and \
                player.party in table.round.exchange:
            exchange = table.round.exchange[player.party]
            if set(msg.get('cards_table_ids')) == set(exchange[player.id]):
                # remove cards from exchanging player
                player.remove_cards(exchange[player.id])
                # get peer id to send cards to
                peer_id = [x for x in exchange if x != player.id][0]
                peer = game.players[peer_id]
                peer.cards += exchange[player.id]
                cards_hand = [Deck.cards[x] for x in Deck.cards if x in peer.cards]
                cards_timestamp = table.round.cards_timestamp
                cards_exchange_count = len(exchange[player.id])
                # if peer has no cards yet put onto table exchange is still in exchange mode
                if not exchange[peer.id]:
                    table_mode = 'exchange'
                else:
                    table_mode = 'normal'
                event = 'exchange-player-cards-to-client'
                payload = {'player_id': peer_id,
                           'table_id': table.id,
                           'cards_exchange_count': cards_exchange_count,
                           'table_mode': table_mode,
                           'html': {'cards_hand': render_template('cards/hand.html',
                                                                  cards_hand=cards_hand,
                                                                  table=table,
                                                                  player=player,
                                                                  cards_timestamp=cards_timestamp),
                                    }}
                room = sessions.get(peer_id)
                # debugging...
                if table.is_debugging:
                    table.log(event, payload, room)
                # ...and action
                socketio.emit(event, payload, room=room)

                # when both players got cards the game can go on
                if exchange[player.id] and \
                        exchange[peer.id]:
                    # as there was no card yet and first player is the [1] because [0] was dealer
                    current_player_id = table.round.players[1]
                    socketio.emit('exchange-players-finished',
                                  {'table_id': table.id,
                                   'sync_count': table.sync_count,
                                   'current_player_id': current_player_id},
                                  room=table.id)


@socketio.on('setup-table-change')
def setup_table(msg):
    """
    Table can be set up from lobby so it makes no sense to limit setup by using check_message()
    """
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
        elif action == 'allow_exchange':
            table.round.allow_exchange = True
        elif action == 'prohibit_exchange':
            table.round.allow_exchange = False
        elif action == 'enable_debugging':
            table.is_debugging = True
        elif action == 'disable_debugging':
            table.is_debugging = False
        elif action == 'changed_order':
            order = msg.get('order')
            # in case there are spectator_only players just check if current active players are included
            if set(table.order).issubset(set(order)):
                table.players = order
        elif action == 'start_table':
            table.start()
            sync_count = table.sync_count
            # just tell everybody to get personal cards
            # for unknown reason this does not seem to be necessary because the connection
            # gets lost in every case and client just tries to reconnect
            socketio.emit('grab-your-cards',
                          {'table_id': table.id,
                           'sync_count': sync_count},
                          room=table.id)
        # # tell others about table change
        elif action == 'finished':
            # tell others about table change
            socketio.emit('index-list-changed',
                          {'table': 'tables'})
    # new tables do not have an id
    elif player and action == 'finished':
        # tell others about table change
        socketio.emit('index-list-changed',
                      {'table': 'tables'})


@socketio.on('setup-player-change')
def setup_player(msg):
    """
    player settings might be set from admin too, so there is no check if current_user.id == player.id
    """
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
        elif action == 'is_spectator_only':
            player.is_spectator_only = True
        elif action == 'not_is_spectator_only':
            player.is_spectator_only = False
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
        elif action == 'finished':
            # tell others about player change
            socketio.emit('index-list-changed',
                          {'table': 'players'})
            # list of tables could use an update too in case player became spectator only
            socketio.emit('index-list-changed',
                          {'table': 'tables'})


@socketio.on('deal-cards')
def deal_cards(msg):
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        table.reset_round()
        # table increases its sync_count when resetting round
        sync_count = table.sync_count
        # just tell everybody to get personal cards
        event = 'grab-your-cards',
        payload = {'table_id': table.id,
                   'sync_count': sync_count}
        room = table.id
        # debugging...
        if table.is_debugging:
            table.log(event, payload, room)
        # ...and action
        socketio.emit(event, payload, room=room)


@socketio.on('deal-cards-again')
def deal_cards_again(msg):
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        sync_count = table.sync_count
        # ask dealer if really should be re-dealt
        socketio.emit('confirm-deal-again',
                      {'table_id': table.id,
                       'sync_count': sync_count,
                       'html': render_template('round/request_deal_again.html',
                                               table=table)},
                      room=request.sid)


@socketio.on('my-cards-please')
def deal_cards_to_player(msg):
    """
    give player cards after requesting them
    """
    msg_ok, player, table = check_message(msg, player_in_round=False)
    if msg_ok:
        dealer = table.dealer
        # just in case
        join_room(table.id)
        current_player_id = table.round.current_player
        cards_timestamp = table.round.cards_timestamp
        exchange_needed = table.round.is_exchange_needed(player.id)
        sync_count = table.sync_count
        if player.id in table.round.players and \
                player.id in table.players_active:
            cards_hand = player.get_cards()
            if table.round.cards_shown:
                # cards_shown contains cqrds-showing player_id
                cards_table = game.players[table.round.cards_shown].get_cards()
            elif exchange_needed:
                cards_table = game.deck.get_cards(table.round.exchange[player.party][player.id])
                # take out the cards from player's hand which lay on table
                cards_hand = [x for x in cards_hand if x.id not in table.round.exchange[player.party][player.id]]
            else:
                cards_table = []
            mode = 'player'
            dealing_needed = table.round.turn_count == 0
            cards_shown = table.round.cards_shown
            # if one trick right now was finished the claim-trick-button should be displayed again
            trick_claiming_needed = table.round.turn_count % 4 == 0 and \
                                    table.round.turn_count > 0 and \
                                    not table.round.is_finished()
            # putting into variables makes debugging easier
            event = 'your-cards-please',
            payload = {'player_id': player.id,
                       'turn_count': table.round.turn_count,
                       'current_player_id': current_player_id,
                       'dealer': dealer,
                       'dealing_needed': dealing_needed,
                       'trick_claiming_needed': trick_claiming_needed,
                       'exchange_needed': exchange_needed,
                       'cards_shown': cards_shown,
                       'sync_count': sync_count,
                       'html': {'cards_hand': render_template('cards/hand.html',
                                                              cards_hand=cards_hand,
                                                              table=table,
                                                              player=player,
                                                              cards_timestamp=cards_timestamp),
                                'hud_players': render_template('top/hud_players.html',
                                                               table=table,
                                                               player=player,
                                                               game=game,
                                                               dealer=dealer,
                                                               current_player_id=current_player_id),
                                'cards_table': render_template('cards/table.html',
                                                               cards_table=cards_table,
                                                               table=table,
                                                               cards_timestamp=cards_timestamp,
                                                               mode=mode)}
                       }
            room = request.sid
            # debugging...
            if table.is_debugging:
                table.log(event, payload, room)
            # ...and action
            socketio.emit(event, payload, room=room)
        else:
            # spectator mode
            players = table.round.players
            players_cards = table.round.get_players_shuffled_cards()
            if table.round.cards_shown:
                # cards_shown contains cqrds-showing player_id
                cards_table = game.players[table.round.cards_shown].get_cards()
            else:
                cards_table = table.round.current_trick.get_cards()
            mode = 'spectator'
            event = 'sorry-no-cards-for-you',
            payload = {'sync_count': sync_count,
                       'html': {'hud_players': render_template('top/hud_players.html',
                                                               table=table,
                                                               player=player,
                                                               game=game,
                                                               dealer=dealer,
                                                               current_player_id=current_player_id),
                                'cards_table': render_template('cards/table.html',
                                                               cards_table=cards_table,
                                                               table=table,
                                                               cards_timestamp=cards_timestamp,
                                                               mode=mode),
                                'cards_hand_spectator_upper': render_template('cards/hand_spectator_upper.html',
                                                                              table=table,
                                                                              players=players,
                                                                              players_cards=players_cards,
                                                                              game=game),
                                'cards_hand_spectator_lower': render_template('cards/hand_spectator_lower.html',
                                                                              table=table,
                                                                              players=players,
                                                                              players_cards=players_cards,
                                                                              game=game)
                                }}
            room = request.sid
            # debugging...
            if table.is_debugging:
                table.log(event, payload, room)
            # ...and action
            socketio.emit(event, payload, room=room)


@socketio.on('sorted-cards')
def sorted_cards(msg):
    """
    while player sorts cards every card placed somewhere causes transmission of current card sort order
    which gets saved here
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        cards_hand_ids = msg.get('cards_hand_ids')
        if set(cards_hand_ids) == set(player.cards):
            player.cards = cards_hand_ids
            player.save()


@socketio.on('claim-trick')
def claimed_trick(msg):
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        sync_count = table.increase_sync_count()
        if not table.round.is_finished():
            # when ownership changes it does at previous trick because normally there is a new one created
            # so the new one becomes the current one and the reclaimed is the previous
            if not len(table.round.current_trick.cards) == 0:
                # old trick, freshly claimed
                table.round.current_trick.owner = player.id
                # new trick for next turns
                table.round.add_trick(player.id)
            else:
                # apparently the ownership of the previous trick is not clear - change it
                table.round.previous_trick.owner = player.id
                table.round.current_player = player.id
            cards_timestamp = table.round.cards_timestamp
            cards_table = []
            table.round.calculate_trick_order()
            table.round.calculate_stats()
            socketio.emit('next-trick',
                          {'current_player_id': player.id,
                           'score': table.round.stats['score'],
                           'table_id': table.id,
                           'sync_count': sync_count,
                           'html': {'hud_players': render_template('top/hud_players.html',
                                                                   table=table,
                                                                   player=player,
                                                                   game=game,
                                                                   current_player_id=player.id),
                                    'cards_table': render_template('cards/table.html',
                                                                   cards_table=cards_table,
                                                                   table=table,
                                                                   cards_timestamp=cards_timestamp)
                                    }},
                          room=table.id)
        else:
            table.round.current_trick.owner = player.id
            players = game.players
            table.round.calculate_stats()
            table.shift_players()
            # tell everybody stats and wait for everybody confirming next round
            socketio.emit('round-finished',
                          {'table_id': table.id,
                           'sync_count': sync_count,
                           'html': render_template('round/score.html',
                                                   table=table,
                                                   players=players)
                           },
                          room=table.id)


@socketio.on('need-final-result')
def send_final_result(msg):
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        players = game.players
        # tell single player stats and wait for everybody confirming next round
        socketio.emit('round-finished',
                      {'table_id': table.id,
                       'sync_count': table.sync_count,
                       'html': render_template('round/score.html',
                                               table=table,
                                               players=players)
                       },
                      room=request.sid)


@socketio.on('ready-for-next-round')
def ready_for_next_round(msg):
    msg_ok, player, table = check_message(msg, player_in_round=False)
    if msg_ok:
        table.add_ready_player(player.id)
        next_players = table.order[:4]
        number_of_rows = max(len(next_players), len(table.idle_players))
        if set(table.players_ready) >= set(table.round.players):
            # now shifted when round is finished
            table.reset_ready_players()
            # just tell everybody to get personal cards
        socketio.emit('start-next-round',
                      {'table_id': table.id,
                       'dealer': table.dealer,
                       'html': render_template('round/info.html',
                                               table=table,
                                               dealer=table.dealer,
                                               next_players=next_players,
                                               game=game,
                                               number_of_rows=number_of_rows)
                       },
                      room=request.sid)


@socketio.on('request-round-finish')
def request_round_finish(msg):
    msg_ok, player, table = check_message(msg)
    if msg_ok:
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
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        table.add_ready_player(player.id)
        if set(table.players_ready) >= set(table.round.players):
            table.shift_players()
            table.reset_ready_players()
            next_players = table.order[:4]
            number_of_rows = max(len(next_players), len(table.idle_players))
            # just tell everybody to get personal cards
            socketio.emit('start-next-round',
                          {'table_id': table.id,
                           'dealer': table.dealer,
                           'html': render_template('round/info.html',
                                                   table=table,
                                                   next_players=next_players,
                                                   game=game,
                                                   number_of_rows=number_of_rows)},
                          room=table.id)


@socketio.on('request-round-reset')
def request_round_reset(msg):
    msg_ok, player, table = check_message(msg)
    if msg_ok:
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
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        table.add_ready_player(player.id)
        if set(table.players_ready) >= set(table.round.players):
            table.reset_round()
            socketio.emit('grab-your-cards',
                          {'table_id': table.id,
                           'sync_count': table.sync_count},
                          room=table.id)


@socketio.on('request-undo')
def request_undo(msg):
    msg_ok, player, table = check_message(msg)
    if msg_ok:
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
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        table.add_ready_player(player.id)
        if set(table.players_ready) >= set(table.round.players):
            table.round.undo()
            socketio.emit('grab-your-cards',
                          {'table_id': table.id},
                          room=table.id)


@socketio.on('request-show-hand')
def request_show_hand(msg):
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        # ask player if cards really should be shown
        socketio.emit('confirm-show-cards',
                      {'table_id': table.id,
                       'sync_count': table.sync_count,
                       'html': render_template('round/request_show_cards.html',
                                               table=table)},
                      room=request.sid)


@socketio.on('show-cards')
def show_cards(msg):
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        table.show_cards(player)
        cards_timestamp = table.round.cards_timestamp
        cards_table = game.players[player.id].get_cards()
        event = 'cards-shown-by-user',
        payload = {'table_id': table.id,
                   'sync_count': table.sync_count,
                   'html': {'cards_table': render_template('cards/table.html',
                                                           cards_table=cards_table,
                                                           table=table,
                                                           cards_timestamp=cards_timestamp)
                            }}
        room = table.id
        # debugging...
        if table.is_debugging:
            table.log(event, payload, room)
        # ...and action
        socketio.emit(event, payload, room=room)


@socketio.on('request-exchange')
def request_exchange(msg):
    """
    player asks for exchange
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        hochzeit = table.round.has_hochzeit()
        exchange_type = 'contra'
        if not hochzeit and player.party == 're':
            exchange_type = 're'
        card_played = table.round.turn_count > 0
        exchanged_already = False
        if table.round.exchange and \
                player.party in table.round.exchange and \
                table.round.exchange[player.party]:
            exchanged_already = True
        # ask player if exchange really should be started
        socketio.emit('confirm-exchange',
                      {'table_id': table.id,
                       'sync_count': table.sync_count,
                       'html': render_template('round/request_exchange.html',
                                               table=table,
                                               hochzeit=hochzeit,
                                               exchange_type=exchange_type,
                                               card_played=card_played,
                                               exchanged_already=exchanged_already
                                               )},
                      room=request.sid)


@socketio.on('exchange-start')
def exchange_ask_player2(msg):
    """
    exchange peer player2 has to be asked
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        player2 = table.round.get_peer(player.id)
        hochzeit = table.round.has_hochzeit()
        exchange_type = 'contra'
        if not hochzeit and player.party == 're':
            exchange_type = 're'
        # ask peer player2 if exchange is ok
        socketio.emit('exchange-ask-player2',
                      {'table_id': table.id,
                       'sync_count': table.sync_count,
                       'html': render_template('round/exchange_ask_player2.html',
                                               game=game,
                                               table=table,
                                               exchange_type=exchange_type,
                                               exchange_player_id=player.id
                                               )},
                      room=sessions.get(player2))


@socketio.on('exchange-player2-ready')
def exchange_player2_ready(msg):
    """
    exchange peer is willing and ready
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        # peer of peer is exchange starting player again - necessary because answer comes from player2
        player1 = table.round.get_peer(player.id)
        if table.round.create_exchange(player1):
            # tell all players that there is an exchange going on
            socketio.emit('exchange-players-starting',
                          {'table_id': table.id,
                           'sync_count': table.sync_count},
                          room=table.id)
            # tell exchange initializing player to finally begin transaction
            socketio.emit('exchange-player1-start',
                          {'table_id': table.id,
                           'sync_count': table.sync_count},
                          room=sessions.get(player1))


@socketio.on('exchange-player2-deny')
def exchange_player2_deny(msg):
    """
    exchange peer doesn't want to exchange
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        # peer of peer is exchange starting player again - necessary because answer comes from player2
        player1 = table.round.get_peer(player.id)
        hochzeit = table.round.has_hochzeit()
        exchange_type = 'contra'
        if not hochzeit and player.party == 're':
            exchange_type = 're'
        # tell exchange initializing player to finally begin transaction
        socketio.emit('exchange-player1-player2-deny',
                      {'table_id': table.id,
                       'sync_count': table.sync_count,
                       'html': render_template('round/exchange_player2_deny.html',
                                               game=game,
                                               table=table,
                                               exchange_type=exchange_type,
                                               exchange_player_id=player.id
                                               )},
                      room=sessions.get(player1))


#
# ------------ Routes ------------
#
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = Login()
    if form.validate_on_submit():
        player_id_quoted = quote(form.player_id.data, safe='')
        player = game.players.get(player_id_quoted)
        if player:
            if not player.check_password(form.password.data):
                flash('Falsches Passwort :-(')
                return redirect(url_for('login'))
            login_user(player)
            return redirect(url_for('index'))
        else:
            flash('Spieler nicht bekannt :-(')
            return redirect(url_for('login'))
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
                               game=game,
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
            exchange_needed = table.round.is_exchange_needed(player.id)
            current_player_id = table.round.current_player
            cards_hand = player.get_cards()
            if table.round.cards_shown:
                # cards_shown contains cqrds-showing player_id
                cards_table = game.players[table.round.cards_shown].get_cards()
            elif exchange_needed:
                cards_table = game.deck.get_cards(table.round.exchange[player.party][player.id])
                # take out the cards from player's hand which lay on table
                cards_hand = [x for x in cards_hand if x.id not in table.round.exchange[player.party][player.id]]
            else:
                cards_table = table.round.current_trick.get_cards()
            cards_timestamp = table.round.cards_timestamp
            cards_shown = table.round.cards_shown
            mode = 'player'
            return render_template('table.html',
                                   title=f"{app.config['TITLE']} {table.name}",
                                   table=table,
                                   dealer=dealer,
                                   dealing_needed=dealing_needed,
                                   trick_claiming_needed=trick_claiming_needed,
                                   exchange_needed=exchange_needed,
                                   player=player,
                                   current_player_id=current_player_id,
                                   cards_hand=cards_hand,
                                   cards_table=cards_table,
                                   cards_timestamp=cards_timestamp,
                                   cards_shown=cards_shown,
                                   game=game,
                                   mode=mode)
        else:
            players = table.round.players
            players_cards = table.round.get_players_shuffled_cards()
            if table.round.cards_shown:
                # cards_shown contains cqrds-showing player_id
                cards_table = game.players[table.round.cards_shown].get_cards()
            else:
                cards_table = table.round.current_trick.get_cards()
            mode = 'spectator'
            return render_template('table.html',
                                   title=f"{app.config['TITLE']} {table.name}",
                                   table=table,
                                   cards_table=cards_table,
                                   player=player,
                                   players=players,
                                   players_cards=players_cards,
                                   game=game,
                                   mode=mode)
    return redirect(url_for('index'))


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
            player = game.players[current_user.get_id()]
            return jsonify({'allowed': True,
                            'html': render_template('setup/table.html',
                                                    table=table,
                                                    player=player,
                                                    game=game)})
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
    support for socket.io request, just telling .button-enter-table if its link can be followed or not
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


@app.route('/get/welcome/<table_id>')
@app.route('/get/welcome')
@login_required
def get_welcome(table_id=None):
    """
    get HTML snippet if welcome on index or table is needed
    """
    if is_xhr(request):
        if table_id:
            table = game.tables.get(table_id)
            if table and table.needs_welcome:
                return jsonify({'needs_welcome': True,
                                'html': render_template('round/welcome.html',
                                                        table=table)})
            else:
                return jsonify({'needs_welcome': False})
        else:
            if game.needs_welcome:
                return jsonify({'needs_welcome': True,
                                'html': render_template('index/welcome.html',
                                                        game=game)})
            else:
                return jsonify({'needs_welcome': False})
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
                                                tables=tables,
                                                game=game)})
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
            new_player_spectator_only = request.values.get('switch_new_player_is_spectator_only', False)
            # convert 'on' from HTML form to True
            if new_player_spectator_only:
                new_player_spectator_only = True
            new_player_allows_spectators = request.values.get('switch_new_player_allows_spectators', False)
            # convert 'on' from HTML form to True
            if new_player_allows_spectators:
                new_player_allows_spectators = True
            if new_player_id:
                if new_player_id in game.players:
                    return jsonify({'status': 'error',
                                    'message': 'Diesen Spieler gibt es schon :-('})
                else:
                    if new_player_password:
                        player = game.add_player(player_id=new_player_id,
                                                 password=new_player_password,
                                                 spectator_only=new_player_spectator_only,
                                                 allows_spectators=new_player_allows_spectators)
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
                return jsonify({'status': 'ok'})
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
                                                        message=f"Es sitzen noch Spieler am Tisch {table.name}.")})
        elif request.method == 'POST':
            if game.delete_table(table.id):
                return jsonify({'status': 'ok'})
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
        if len(table.players_active) >= 4:
            return jsonify({'status': 'ok',
                            'html': render_template('index/start_table.html',
                                                    table=table)})
        else:
            return jsonify({'status': 'error',
                            'html': render_template('error.html',
                                                    message='Es sitzen nicht genug Spieler am Tisch.'
                                                    )})
    else:
        return redirect(url_for('index'))
