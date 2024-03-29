from time import time

from flask import flash, \
    Flask, \
    jsonify, \
    redirect, \
    render_template, \
    request, \
    url_for
from flask_compress import Compress
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
from .misc import get_hash, \
    is_xhr, \
    MESSAGE_LOGIN_FAILURE

# needed for ajax detection
ACCEPTED_JSON_MIMETYPES = ['*/*', 'text/javascript', 'application/json']

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
# enable compression of static files
compress = Compress(app)
# extend by socket.io
# shorter ping interval for better sync
socketio = SocketIO(app,
                    path='/doko3000.io',
                    manage_session=False,
                    ping_timeout=30,
                    ping_interval=1,
                    logger=Config.DEBUG,
                    engineio_logger=Config.DEBUG,
                    cors_allowed_origins=Config.CORS_ALLOWED_ORIGINS)

# load game data from database after initialization
game = Game(db)

# keep track of players and their sessions to enable directly emitting a socketio event
sessions = {}


@login.user_loader
def load_user(id):
    """
    give user back if it exists, otherwise force login
    """
    player = game.players.get(id)
    if player:
        return player
    else:
        return None


# no decorator possible for socketio.on-events so make this a function
def check_message(msg, player_in_round=True, player_at_table=True):
    """
    check if message is correctly sent from player
    tries to avoid permanently repeated code

    player_in_round is important if there are more than 4 players - the fifth is at table but not in round
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
    """
    sent by client at connection creation and if connection was refreshed
    provide the important information about the game
    """
    if not current_user.is_anonymous:
        player = game.players.get(current_user.id)
        if player:
            table = game.tables.get(player.table)
            # store player session for later usage
            sessions[player.id] = request.sid
            # if player already sits on a table inform client
            if table:
                current_player_id = table.round.current_player_id
                join_room(table.id)
                table_id = table.id
                sync_count = table.sync_count
                round_finished = table.round.is_finished
                round_reset = table.round.is_reset
            else:
                current_player_id = ''
                table_id = ''
                # nonexisting table has no own sync_count
                sync_count = 0
                round_finished = False
                round_reset = False
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
            socketio.emit(event, payload, to=room)


@socketio.on('enter-table')
def enter_table_socket(msg):
    """
    sent if player wants to enter a table - allowed if table is not locked
    """
    msg_ok, player, table = check_message(msg, player_in_round=False, player_at_table=False)
    if msg_ok:
        if (table.locked and player.id in table.players) or \
                not (table.locked and not player.is_admin):
            # store old table if it exists to be able to send it a updated HUD too
            if player.table:
                table_old = game.tables.get(player.table)
            else:
                table_old = None
            game.tables[table.id].add_player(player.id)
            join_room(table.id)
            # check if any formerly locked table is now emtpy and should be unlocked
            game.check_tables()
            socketio.emit('index-list-changed',
                          {'table': 'tables'})
            # send message to old table and new one to update HUD on old table too
            for target_table in [table_old, table]:
                if target_table:
                    socketio.emit('hud-changed',
                                  {'html': {'hud_players': render_template('top/hud_players.html',
                                                                           table=target_table,
                                                                           player=player,
                                                                           game=game)
                                            }},
                                  to=target_table.id
                                  )


@socketio.on('card-played')
def played_card(msg):
    """
    sent when a player played a card, update table and tell all other clients
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        card_id = msg.get('card_id')
        # check if cards on hand are correct
        cards_hand_ids = msg.get('cards_hand_ids')
        if set(cards_hand_ids) | {card_id} == set(player.cards) and \
                len(cards_hand_ids) + 1 == len(player.cards):
            if card_id in Deck.cards and \
                    len(table.round.current_trick.cards) < 4 and \
                    current_user.id == player.id == table.round.current_player_id:
                table.round.current_trick.add_turn(player.id, card_id)
                table.round.increase_turn_count()
                card = Deck.cards[card_id]
                player.remove_card(card.id)
                current_player_id = table.round.get_current_player_id()
                if table.round.player_showing_hand:
                    # player_showing_hand contains cards-showing player_id
                    cards_table = game.players[table.round.player_showing_hand].get_cards()
                else:
                    cards_table = table.round.current_trick.get_cards()
                table.increase_sync_count()
                event = 'card-played-by-player'
                payload = {'player_id': player.id,
                           'table_id': table.id,
                           'card_id': card.id,
                           'card_name': card.name,
                           'is_last_turn': table.round.current_trick.is_last_turn,
                           'current_player_id': current_player_id,
                           'players_idle': table.players_idle,
                           'players_spectator_only': table.players_spectator_only,
                           'played_cards': table.round.played_cards,
                           'player_showing_hand': table.round.player_showing_hand,
                           'sync_count': table.sync_count,
                           'html': {'cards_table': render_template('cards/table.html',
                                                                   cards_table=cards_table,
                                                                   table=table,
                                                                   game=game),
                                    'hud_players': render_template('top/hud_players.html',
                                                                   table=table,
                                                                   player=player,
                                                                   game=game)
                                    }}
                room = table.id
                # debugging...
                if table.is_debugging:
                    table.log(event, payload, room)
                # ...and action
                socketio.emit(event, payload, to=room)
        else:
            deliver_cards_to_player(msg)


@socketio.on('card-exchanged')
def card_exchanged(msg):
    """
    sent if re/contra exchange succeeded
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        exchange_hash = get_hash(player.id, player.exchange_peer_id)
        if table.round.exchange and \
                exchange_hash in table.round.exchange:
            cards_table_ids = msg.get('cards_table_ids')
            if cards_table_ids:
                table.round.update_exchange(player.id, cards_table_ids)


@socketio.on('exchange-player-cards-to-server')
def exchange_player_cards(msg):
    """
    both stages of card exchange fire this message up, each transmitting its exchanged cards
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        exchange_hash = get_hash(player.id, player.exchange_peer_id)
        if table.round.exchange and \
                table.round.exchange.get(exchange_hash):
            exchange = table.round.exchange[exchange_hash]
            if set(msg.get('cards_table_ids')) == set(exchange[player.id]):
                # remove cards from exchanging player
                player.remove_cards(exchange[player.id])
                # get peer id to send cards to
                peer = game.players[player.exchange_peer_id]
                peer.cards += exchange[player.id]
                cards_hand = [Deck.cards[x] for x in peer.cards]
                cards_exchange_count = len(exchange[player.id])
                # if peer has no cards yet put onto table exchange is still in exchange mode
                if not exchange[peer.id]:
                    table_mode = 'exchange'
                else:
                    table_mode = 'normal'
                event = 'exchange-player-cards-to-client'
                payload = {'player_id': player.exchange_peer_id,
                           'table_id': table.id,
                           'cards_exchange_count': cards_exchange_count,
                           'table_mode': table_mode,
                           'html': {'cards_hand': render_template('cards/hand.html',
                                                                  cards_hand=cards_hand,
                                                                  table=table,
                                                                  player=player,
                                                                  game=game),
                                    }}
                room = sessions.get(player.exchange_peer_id)
                # debugging...
                if table.is_debugging:
                    table.log(event, payload, room)
                # ...and action
                socketio.emit(event, payload, to=room)

                # when both players got cards the game can go on
                if exchange[player.id] and \
                        exchange[peer.id]:
                    # as there was no card yet and first player is the [1] because [0] was dealer
                    current_player_id = table.round.players[1]
                    socketio.emit('exchange-players-finished',
                                  {'table_id': table.id,
                                   'sync_count': table.sync_count,
                                   'current_player_id': current_player_id},
                                  to=table.id)
                    # finally clear exchange
                    table.round.reset_exchange()


@socketio.on('setup-table-change')
def setup_table(msg):
    """
    table can be set up from lobby so it makes no sense to limit setup by using check_message()
    """
    # check_message makes more trouble here than being of use
    player = game.players.get(msg.get('player_id'))
    table = game.tables.get(msg.get('table_id'))
    action = msg.get('action')
    if player and table:
        if action == 'remove_player':
            table.remove_player(player.id)
            # tell others about table change
            socketio.emit('index-list-changed',
                          {'table': 'tables'})
        elif action == 'lock_table':
            table.locked = True
            # tell others about table change
            socketio.emit('index-list-changed',
                          {'table': 'tables'})
        elif action == 'unlock_table':
            table.locked = False
            # tell others about table change
            socketio.emit('index-list-changed',
                          {'table': 'tables'})
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
            # when player sits on table and starts from start page it shall be redirected directly to its table
            if not '/table/' in request.referrer and \
                    player.id in table.players:
                socketio.emit('redirect-to-path',
                              {'path': f'/table/{table.id}'},
                              to=request.sid)
            else:
                # just tell everybody to get personal cards
                # for unknown reason this does not seem to be necessary because the connection
                # gets lost in every case and client just tries to reconnect
                socketio.emit('grab-your-cards',
                              {'table_id': table.id,
                               'sync_count': table.sync_count},
                              to=table.id)
        # tell others about table change
        elif action == 'finished':
            # tell others about table change
            socketio.emit('index-list-changed',
                          {'table': 'tables'})
    # new tables do not have an id, so check_msg would fail
    # only of interest on index page
    elif player and action == 'finished':
        # tell others about table change
        socketio.emit('index-list-changed',
                      {'table': 'tables'})


@socketio.on('setup-player-change')
def setup_player(msg):
    """
    player settings might be set from admin too, so there is no check if current_user.id == player.id
    """
    player = game.players.get(msg.get('player_id'))
    action = msg.get('action')
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
                              to=request.sid)
            else:
                socketio.emit('change-password-failed',
                              {'player_id': player.id},
                              to=request.sid)
        elif action == 'finished':
            # tell others about player change
            socketio.emit('index-list-changed',
                          {'table': 'players'})
            # list of tables could use an update too in e.g. case player became spectator only
            socketio.emit('index-list-changed',
                          {'table': 'tables'})


@socketio.on('deal-cards')
def deal_cards(msg):
    """
    dealer triggers distribution of cards to players
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        # table increases its sync_count when resetting round
        table.reset_round()
        # just tell everybody to get personal cards
        event = 'grab-your-cards'
        payload = {'table_id': table.id,
                   'sync_count': table.sync_count}
        room = table.id
        # debugging...
        if table.is_debugging:
            table.log(event, payload, room)
        # ...and action
        socketio.emit(event,
                      payload,
                      to=room)


@socketio.on('deal-cards-again')
def deal_cards_again(msg):
    """
    current dealer pressed the deal-again-button
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        # ask dealer if really should be re-dealt
        socketio.emit('confirm-deal-again',
                      {'table_id': table.id,
                       'sync_count': table.sync_count,
                       'html': render_template('round/request_deal_again.html',
                                               table=table)},
                      to=request.sid)


@socketio.on('my-cards-please')
def deliver_cards_to_player(msg):
    """
    give player cards after requesting them
    """
    msg_ok, player, table = check_message(msg, player_in_round=False)
    if msg_ok:
        # just in case
        join_room(table.id)
        exchange_needed = table.round.is_exchange_needed(player.id)
        if player.id in table.round.players and \
                player.id in table.players_active:
            cards_hand = player.get_cards()
            if table.round.player_showing_hand:
                # player_showing_hand contains cards-showing player_id
                cards_table = game.players[table.round.player_showing_hand].get_cards()
            elif exchange_needed:
                exchange_hash = get_hash(player.id, player.exchange_peer_id)
                cards_table = game.deck.get_cards(table.round.exchange[exchange_hash][player.id])
                # take out the cards from player's hand which lay on table
                cards_hand = [x for x in cards_hand if x.id not in table.round.exchange[exchange_hash][player.id]]
            else:
                cards_table = []
            mode = 'player'
            # putting into variables makes debugging easier
            event = 'your-cards-please'
            payload = {'player_id': player.id,
                       'table_id': table.id,
                       'turn_count': table.round.turn_count,
                       'current_player_id': table.round.current_player_id,
                       'dealer': table.dealer,
                       'needs_dealing': table.round.needs_dealing,
                       'needs_trick_claiming': table.round.needs_trick_claiming,
                       'exchange_needed': exchange_needed,
                       'player_showing_hand': table.round.player_showing_hand,
                       'sync_count': table.sync_count,
                       'cards_per_player': table.round.cards_per_player,
                       'html': {'cards_hand': render_template('cards/hand.html',
                                                              cards_hand=cards_hand,
                                                              table=table,
                                                              player=player,
                                                              game=game),
                                'hud_players': render_template('top/hud_players.html',
                                                               table=table,
                                                               player=player,
                                                               game=game),
                                'cards_table': render_template('cards/table.html',
                                                               cards_table=cards_table,
                                                               table=table,
                                                               game=game,
                                                               mode=mode)}
                       }
            room = request.sid
            # debugging...
            if table.is_debugging:
                table.log(event, payload, room)
            # ...and action
            socketio.emit(event, payload, to=room)
        elif not table.needs_welcome:
            # spectator mode
            players_cards = table.round.get_players_shuffled_cards()
            if table.round.player_showing_hand:
                # player_showing_hand contains cards-showing player_id
                cards_table = game.players[table.round.player_showing_hand].get_cards()
            else:
                cards_table = table.round.current_trick.get_cards()
            mode = 'spectator'
            event = 'sorry-no-cards-for-you'
            payload = {'sync_count': table.sync_count,
                       'html': {'hud_players': render_template('top/hud_players.html',
                                                               table=table,
                                                               player=player,
                                                               game=game),
                                'cards_table': render_template('cards/table.html',
                                                               cards_table=cards_table,
                                                               table=table,
                                                               mode=mode),
                                'cards_hand_spectator_upper': render_template('cards/hand_spectator_upper.html',
                                                                              table=table,
                                                                              players_cards=players_cards,
                                                                              game=game),
                                'cards_hand_spectator_lower': render_template('cards/hand_spectator_lower.html',
                                                                              table=table,
                                                                              players_cards=players_cards,
                                                                              game=game)
                                }}
            room = request.sid
            # debugging...
            if table.is_debugging:
                table.log(event, payload, room)
            # ...and action
            socketio.emit(event, payload, to=room)


@socketio.on('sorted-cards')
def sorted_cards(msg):
    """
    while player sorts cards every card placed somewhere causes transmission of current card sort order
    which gets saved here
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        cards_hand_ids = msg.get('cards_hand_ids')
        # send player its real cards back if cards on client don't match the ones on server
        if set(cards_hand_ids) == set(player.cards) and \
                len(cards_hand_ids) == len(player.cards):
            player.cards = cards_hand_ids
            player.save()
        else:
            deliver_cards_to_player(msg)


@socketio.on('claim-trick')
def claim_trick(msg):
    """
    when all players played their cards someone will claim the trick
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        table.increase_sync_count()
        if not table.round.is_finished:
            # when ownership changes it does at previous trick because normally there is a new one created
            # so the new one becomes the current one and the reclaimed is the previous
            if not len(table.round.current_trick.cards) == 0:
                # makes player owner of trick
                table.round.take_trick(player.id)
            else:
                # apparently the ownership of the previous trick is not clear - change it
                table.round.previous_trick.owner = player.id
                table.round.current_player_id = player.id
            cards_table = []
            table.round.calculate_trick_order()
            table.round.calculate_stats()

            socketio.emit('next-trick',
                          {'current_player_id': player.id,
                           'score': table.round.stats['score'],
                           'table_id': table.id,
                           'sync_count': table.sync_count,
                           'html': {'hud_players': render_template('top/hud_players.html',
                                                                   table=table,
                                                                   player=player,
                                                                   game=game),
                                    'cards_table': render_template('cards/table.html',
                                                                   cards_table=cards_table,
                                                                   table=table)
                                    }},
                          to=table.id)
        else:
            table.round.current_trick.owner = player.id
            table.round.calculate_stats()
            table.shift_players()
            # tell everybody stats and wait for everybody confirming next round
            socketio.emit('round-finished',
                          {'table_id': table.id,
                           'sync_count': table.sync_count,
                           'html': render_template('round/score.html',
                                                   table=table,
                                                   game=game)
                           },
                          to=table.id)


@socketio.on('need-final-result')
def need_final_result(msg):
    """
    at the end of the round the resulting score will be shown to the players
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        # tell single player stats and wait for everybody confirming next round
        socketio.emit('round-finished',
                      {'table_id': table.id,
                       'sync_count': table.sync_count,
                       'html': render_template('round/score.html',
                                               table=table,
                                               game=game)
                       },
                      to=request.sid)


@socketio.on('ready-for-next-round')
def ready_for_next_round(msg):
    """
    every player commits being ready for the next round
    """
    msg_ok, player, table = check_message(msg, player_in_round=False)
    if msg_ok:
        table.add_ready_player(player.id)
        next_players = table.order[:4]
        number_of_rows = max(len(next_players), len(table.players_idle))
        # if set(table.players_ready) >= set(table.round.players):
        #     # now shifted when round is finished
        #     table.reset_ready_players()
        # just tell everybody to get personal cards
        # to avoid future errors: this block should NOT be indented, it is already as intended
        socketio.emit('start-next-round',
                      {'table_id': table.id,
                       'dealer': table.dealer,
                       'html': render_template('round/info.html',
                                               table=table,
                                               next_players=next_players,
                                               game=game,
                                               number_of_rows=number_of_rows)
                       },
                      to=request.sid)


@socketio.on('ready-for-next-round-and-read-info')
def round_reset(msg):
    """
    players confirm restarting the round
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        # notify other players clients so they can update the waiting progress indicator
        socketio.emit('ready-player-added',
                      {'table_id': table.id,
                       'player_ready_id': player.id})


@socketio.on('request-round-finish')
def request_round_finish(msg):
    """
    players want to skip and finish the round
    """
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
                      to=table.id)


@socketio.on('ready-for-round-finish')
def round_finish(msg):
    """
    players confirm to finish the round
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        table.add_ready_player(player.id)
        # notify other players clients so they can update the waiting progress indicator
        socketio.emit('ready-player-added',
                      {'table_id': table.id,
                       'player_ready_id': player.id})
        if set(table.players_ready) >= set(table.round.players):
            table.shift_players()
            table.reset_ready_players()
            next_players = table.order[:4]
            number_of_rows = max(len(next_players), len(table.players_idle))
            # just tell everybody to get personal cards
            socketio.emit('start-next-round',
                          {'table_id': table.id,
                           'dealer': table.dealer,
                           'html': render_template('round/info.html',
                                                   table=table,
                                                   next_players=next_players,
                                                   game=game,
                                                   number_of_rows=number_of_rows)},
                          to=table.id)


@socketio.on('request-round-reset')
def request_round_reset(msg):
    """
    round shall be restarted
    """
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
                      to=table.id)


@socketio.on('ready-for-round-reset')
def round_reset(msg):
    """
    players confirm restarting the round
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        table.add_ready_player(player.id)
        # notify other players clients so they can update the waiting progress indicator
        socketio.emit('ready-player-added',
                      {'table_id': table.id,
                       'player_ready_id': player.id})
        if set(table.players_ready) >= set(table.round.players):
            table.reset_round()
            socketio.emit('grab-your-cards',
                          {'table_id': table.id,
                           'sync_count': table.sync_count},
                          to=table.id)


@socketio.on('request-undo')
def request_undo(msg):
    """
    players request reverting the last trick
    """
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
                          to=table.id)


@socketio.on('ready-for-undo')
def round_undo(msg):
    """
    players confirm reverting the last trick
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        table.add_ready_player(player.id)
        # notify other players clients so they can update the waiting progress indicator
        socketio.emit('ready-player-added',
                      {'table_id': table.id,
                       'player_ready_id': player.id})
        if set(table.players_ready) >= set(table.round.players):
            table.round.undo()
            socketio.emit('grab-your-cards',
                          {'table_id': table.id},
                          to=table.id)


@socketio.on('request-show-hand')
def request_show_hand(msg):
    """
    player wants a shortcut and show the cards on hand
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        # ask player if cards really should be shown
        socketio.emit('confirm-show-hand',
                      {'table_id': table.id,
                       'sync_count': table.sync_count,
                       'html': render_template('round/request_show_hand.html',
                                               table=table)},
                      to=request.sid)


@socketio.on('show-hand')
def show_hand(msg):
    """
    player shows cards
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        table.show_hand(player)
        cards_table = game.players[player.id].get_cards()
        event = 'cards-shown-by-player'
        payload = {'table_id': table.id,
                   'sync_count': table.sync_count,
                   'html': {'cards_table': render_template('cards/table.html',
                                                           cards_table=cards_table,
                                                           table=table,
                                                           game=game)
                            }}
        room = table.id
        # debugging...
        if table.is_debugging:
            table.log(event, payload, room)
        # ...and action
        socketio.emit(event, payload, to=room)


@socketio.on('request-exchange')
def request_exchange(msg):
    """
    player asks for exchange
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok and \
            not table.round.card_played and \
            not table.round.exchange:
        # lock table for players
        players_for_exchange = [x for x in game.players.values() if x.id != player.id and x.id in table.round.players]
        socketio.emit('player1-requested-exchange',
                      {'table_id': table.id,
                       'sync_count': table.sync_count},
                      to=table.id)
        # ask player if exchange really should be started or tell it is not possible
        socketio.emit('confirm-exchange',
                      {'table_id': table.id,
                       'sync_count': table.sync_count,
                       'html': render_template('round/request_exchange.html',
                                               table=table,
                                               players_for_exchange=players_for_exchange
                                               )},
                      to=request.sid)


@socketio.on('exchange-start')
def exchange_ask_player2(msg):
    """
    exchange peer player2 has to be asked
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok and \
            msg.get('player2_id') in table.round.players and \
            msg.get('player2_id') != player.id:
        player2_id = msg.get('player2_id')
        if game.players.get(player2_id) and \
                sessions.get(player2_id):
            player.exchange_new(peer_id=player2_id)
            game.players.get(player2_id).exchange_new(player.id)
            # ask peer player2 if exchange is ok
            socketio.emit('exchange-ask-player2',
                          {'table_id': table.id,
                           'sync_count': table.sync_count,
                           'player1_id': player.exchange_peer_id,
                           'html': render_template('round/exchange_ask_player2.html',
                                                   game=game,
                                                   table=table,
                                                   player1_id=player.id
                                                   )},
                          to=sessions.get(player.exchange_peer_id))


@socketio.on('exchange-cancel-player1')
def exchange_cancel(msg):
    """
    the initiating player 1 canceled the exchange - all other players need to know to get their tables unlocked
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        # no need for obsolete exchange peer
        player.exchange_clear()
        current_player_id = table.round.current_player_id
        # cancelling is the same like being finished so just send the already teated event
        socketio.emit('exchange-players-finished',
                      {'table_id': table.id,
                       'sync_count': table.sync_count,
                       'current_player_id': current_player_id},
                      to=table.id)


@socketio.on('exchange-player2-ready')
def exchange_player2_ready(msg):
    """
    exchange peer is willing and ready
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        # peer of peer is exchange starting player again - necessary because answer comes from player2
        player1_id = msg.get('player1_id')
        if game.players.get(player1_id) and \
                game.players.get(player1_id).exchange_peer_id == player.id and \
                sessions.get(player1_id):
            player.exchange_new(peer_id=player1_id)
            if table.round.create_exchange(player1_id=player1_id, player2_id=player.id):
                # tell all players that there is an exchange going on
                socketio.emit('exchange-players-starting',
                              {'table_id': table.id,
                               'sync_count': table.sync_count},
                              to=table.id)
                # tell exchange initializing player to finally begin transaction
                socketio.emit('exchange-player1-start',
                              {'table_id': table.id,
                               'sync_count': table.sync_count},
                              to=sessions.get(player1_id))


@socketio.on('exchange-player2-deny')
def exchange_player2_deny(msg):
    """
    exchange peer doesn't want to exchange
    """
    msg_ok, player, table = check_message(msg)
    if msg_ok:
        # tell everybody that there will be no exchange
        socketio.emit('player2-denied-exchange',
                      {'table_id': table.id,
                       'sync_count': table.sync_count},
                      to=table.id)
        # tell exchange initializing player that second player doesn't want to exchange cards
        socketio.emit('exchange-player1-player2-deny',
                      {'table_id': table.id,
                       'sync_count': table.sync_count,
                       'html': render_template('round/exchange_player2_deny.html',
                                               game=game,
                                               table=table,
                                               exchange_player_id=player.id
                                               )},
                      to=sessions.get(player.exchange_peer_id))
        # exchange peer id is still needed for sending message via socket.io
        player.exchange_clear()
        if game.players.get(player.exchange_peer_id):
            game.players.get(player.exchange_peer_id).exchange_clear()


#
# ------------ Routes ------------
#
@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    non-logged-in players get redirected here
    """
    form_values = list(request.values.keys())
    if 'name' in form_values and \
            'password' in form_values and \
            'submit' in form_values:
        player = game.get_player(request.values['name'])
        if player:
            if not player.check_password(request.values['password']):
                flash(MESSAGE_LOGIN_FAILURE)
            else:
                login_user(player, remember=True)
                return redirect(url_for('index'))
        else:
            flash(MESSAGE_LOGIN_FAILURE)
    # got to login if not logged in
    return render_template('login.html',
                           title=f"{app.config['TITLE']} Login")


@app.route('/logout')
def logout():
    """
    byebye
    """
    logout_user()
    return redirect(url_for('login'))


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """
    the lobby where tables are accessible and admins can create new players
    """
    players = sorted(game.players.values(), key=lambda x: x.name.lower())
    tables = sorted(game.tables.values(), key=lambda x: x.name.lower())
    player = game.players.get(current_user.get_id())
    if player:
        return render_template('index.html',
                               tables=tables,
                               players=players,
                               player=player,
                               game=game,
                               title=f"{app.config['TITLE']}")
    # default return if nothing applies - better do login
    return redirect(url_for('login'))


@app.route('/table/<table_id>')
@login_required
def table(table_id=''):
    """
    one of the tables to play
    """
    player = game.players.get(current_user.id)
    table = game.tables.get(table_id)
    if player and \
            table and \
            player.id in table.players:
        if player.id in table.round.players:
            exchange_needed = table.round.is_exchange_needed(player.id)
            cards_hand = player.get_cards()
            if table.round.player_showing_hand:
                # player_showing_hand contains cards-showing player_id
                cards_table = game.players[table.round.player_showing_hand].get_cards()
            elif exchange_needed:
                exchange_hash = get_hash(player.id, player.exchange_peer_id)
                cards_table = game.deck.get_cards(table.round.exchange[exchange_hash][player.id])
                # take out the cards from player's hand which lay on table
                cards_hand = [x for x in cards_hand if x.id not in table.round.exchange[exchange_hash][player.id]]
            else:
                cards_table = table.round.current_trick.get_cards()
            mode = 'player'
            return render_template('table.html',
                                   title=f"{app.config['TITLE']} {table.name}",
                                   table=table,
                                   exchange_needed=exchange_needed,
                                   player=player,
                                   cards_hand=cards_hand,
                                   cards_table=cards_table,
                                   game=game,
                                   mode=mode)
        else:
            players_cards = table.round.get_players_shuffled_cards()
            if table.round.player_showing_hand:
                # player_showing_hand contains cards-showing player_id
                cards_table = game.players[table.round.player_showing_hand].get_cards()
            else:
                cards_table = table.round.current_trick.get_cards()
            mode = 'spectator'
            return render_template('table.html',
                                   title=f"{app.config['TITLE']} {table.name}",
                                   table=table,
                                   cards_table=cards_table,
                                   player=player,
                                   players_cards=players_cards,
                                   game=game,
                                   mode=mode)
    # default return if nothing applies
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
                current_user.id in game.players and \
                (current_user.id in table.players or
                 not (table.locked and not current_user.is_admin)):
            player = game.players[current_user.id]
            return jsonify({'allowed': True,
                            'html': render_template('setup/table.html',
                                                    table=table,
                                                    player=player,
                                                    game=game)})
        else:
            return jsonify({'allowed': False})
    # default return if nothing applies
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
    # default return if nothing applies
    return redirect(url_for('index'))


@app.route('/enter/table/<table_id>/<player_id>')
@login_required
def enter_table_json(table_id='', player_id=''):
    """
    give enter table permission or not, depending on player membership or table lockedness
    support for socket.io request, just telling .button-enter-table if its link can be followed or not
    """
    if is_xhr(request) and table_id:
        allowed = False
        player = game.players.get(player_id)
        table = game.tables.get(table_id)
        if player and \
                table and \
                ((table.locked and player_id in table.players) or
                 not (table.locked and not player.is_admin)):
            allowed = True
        return jsonify({'allowed': allowed})
    # default return if nothing applies
    return redirect(url_for('index'))


@app.route('/get/welcome/<table_id>')
@app.route('/get/welcome')
@login_required
def get_welcome(table_id=''):
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
    # default return if nothing applies
    return redirect(url_for('index'))


@app.route('/get/tables')
@login_required
def get_tables():
    """
    get HTML list of tables to refresh index.html tables list after changes
    """
    if is_xhr(request):
        tables = sorted(game.tables.values(), key=lambda x: x.name.lower())
        return jsonify({'html': render_template('index/list_tables.html',
                                                tables=tables,
                                                game=game)})
    # default return if nothing applies
    return redirect(url_for('index'))


@app.route('/get/players')
@login_required
def get_players():
    """
    get HTML list of players to refresh index.html players list after changes
    """
    if is_xhr(request):
        players = sorted(game.players.values(), key=lambda x: x.name.lower())
        return jsonify({'html': render_template('index/list_players.html',
                                                players=players)})
    # default return if nothing applies
    return redirect(url_for('index'))


@app.route('/get/wait/<table_id>/<player_id>')
@login_required
def get_wait(table_id='', player_id=''):
    """
    get HTML snippet asking for patience
    """
    if is_xhr(request) and table_id:
        player = game.players.get(player_id)
        table = game.tables.get(table_id)
        if player and \
                table and \
                player_id in table.players:
            players_round = [x for x in game.players.values() if x.id in table.round.players]
            return jsonify({'html': render_template('round/wait.html',
                                                    table=table,
                                                    players_round=players_round,
                                                    player=player)})
    # default return if nothing applies
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
            new_table_name = request.values.get('new_table_name')
            if new_table_name:
                if game.get_table(new_table_name):
                    return jsonify({'status': 'error',
                                    'message': 'Diesen Tisch gibt es schon :-('})
                else:
                    game.add_table(new_table_name)
                    return jsonify({'status': 'ok'})
            else:
                return jsonify({'status': 'error',
                                'message': 'Der Tisch braucht einen Namen'})
    # default return if nothing applies
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
            new_player_name = request.values.get('new_player_name')
            new_player_password = request.values.get('new_player_password')
            new_player_spectator_only = request.values.get('switch_new_player_is_spectator_only', False)
            # convert 'on' from HTML form to True
            if new_player_spectator_only:
                new_player_spectator_only = True
            new_player_allows_spectators = request.values.get('switch_new_player_allows_spectators', False)
            # convert 'on' from HTML form to True
            if new_player_allows_spectators:
                new_player_allows_spectators = True
            if new_player_name:
                if game.get_player(new_player_name):
                    return jsonify({'status': 'error',
                                    'message': 'Diesen Spieler gibt es schon :-('})
                else:
                    if new_player_password:
                        game.add_player(name=new_player_name,
                                        password=new_player_password,
                                        is_spectator_only=new_player_spectator_only,
                                        allows_spectators=new_player_allows_spectators)
                        return jsonify({'status': 'ok'})
                    else:
                        return jsonify({'status': 'error',
                                        'message': 'Der Spieler braucht eine Passwort'})
            else:
                return jsonify({'status': 'error',
                                'message': 'Der Spieler braucht einen Namen'})
    # default return if nothing applies
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
            if not player.is_playing:
                return jsonify({'status': 'ok',
                                'html': render_template('index/delete_player.html',
                                                        player=player)})
            else:
                table = game.tables.get(player.table)
                return jsonify({'status': 'error',
                                'html': render_template('error.html',
                                                        message=f"{player.name} sitzt noch am Tisch {table.name}.")})
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
    # default return if nothing applies
    return redirect(url_for('index'))


@app.route('/get/info')
@login_required
def info():
    """
    Show info about doko3000
    :return:
    """
    if is_xhr(request):
        return jsonify({'status': 'ok',
                        'html': render_template('info.html')})
    # default return if nothing applies
    return redirect(url_for('index'))


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    """
    catch all rule
    """
    return redirect(url_for('index'))
