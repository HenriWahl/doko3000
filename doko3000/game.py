# game logic part of doko3000
from copy import deepcopy
from json import dumps
from os import environ
from pathlib import Path
from random import seed, \
    shuffle
from time import time

# from cloudant.document import Document
from flask_login import UserMixin
from werkzeug.security import check_password_hash, \
    generate_password_hash

from .database import Document3000
from .misc import get_hash


class Card:
    """
    one single card
    """

    def __init__(self, symbol, rank_item, card_id):
        """
        symbol, rank and value come from deck
        """
        self.symbol = symbol
        # value is needed for counting score at the end
        self.rank, self.value = rank_item
        # name comes from symbol and rank
        self.name = f'{self.symbol}-{self.rank}'
        # id comes from deck
        self.id = card_id


class Deck:
    """
    full deck of cards - enough to be static
    """
    if environ.get('DOKO3000_DEVEL_REDUCED_CARD_SET') and \
            environ.get('DOKO3000_DEVEL_REDUCED_CARD_SET').lower() in ['1', 'true', 'yes']:
        SYMBOLS = ('Schell',
                   'Eichel')
        RANKS = {'Zehn': 10,
                 'Ass': 11}
    else:
        SYMBOLS = ('Schell',
                   'Herz',
                   'Grün',
                   'Eichel')
        RANKS = {'Neun': 0,
                 'Zehn': 10,
                 'Unter': 2,
                 'Ober': 3,
                 'König': 4,
                 'Ass': 11}
    NUMBER = 2  # Doppelkopf :-)!

    # containing all cards
    cards = {}
    # counter for card IDs in deck
    card_id = 0
    # fill cards dict
    for number in range(NUMBER):
        for symbol in SYMBOLS:
            for rank in RANKS.items():
                cards[card_id] = Card(symbol, rank, card_id)
                card_id += 1

    # expect SVG cards being default
    file_extension = 'svg'

    def __init__(self):
        """
        find out if there are SVG images available at initialization
        """
        for card in self.cards:
            svg_path = Path(f'doko3000/static/img/cards/{self.cards[card].name}.svg')
            if not (svg_path.exists() and svg_path.is_file()):
                self.file_extension = 'png'
                return None
        # the card back image also has to exist and preferably be SVG
        if not (Path(f'doko3000/static/img/cards/back.svg').exists() and Path(
                f'doko3000/static/img/cards/back.svg').is_file()):
            self.file_extension = 'png'

    def get_cards(self, cards_ids):
        """
        return card objects of card IDs in cards_ids list
        """
        cards = []
        for card_id in cards_ids:
            cards.append(self.cards[card_id])
        return cards


class Player(UserMixin, Document3000):
    """
    one single player on a table

    due to CouchDB Document class everything is now a dictionary
    """

    def __init__(self, name='', document=None, game=None):
        # access to global game
        self.game = game
        if name:
            self['_id'] = self.game.create_player_id()
            super().__init__(database=self.game.db.database)
            # type is for CouchDB
            self['type'] = 'player'
            # name of player - to become somewhat more natural
            self['name'] = name
            # password hash
            self['password_hash'] = ''
            # current set of cards
            self['cards'] = []
            # which table player sits on
            self['table'] = ''
            # has admin rights
            self['is_admin'] = False
            # let idle players see player's cards
            self['allows_spectators'] = True
            # only watches other players playing
            self['is_spectator_only'] = False
            # manage exchanges
            self['exchange_peer_id'] = ''
            self.save()
        elif document:
            super().__init__(database=self.game.db.database, document_id=document['_id'])
            # get data from given document
            self.update(document)

    @property
    def id(self):
        # meanwhile returns CouchDB ID
        return self.get('_id')

    @property
    def name(self):
        return self.get('name', '')

    @property
    def password_hash(self):
        return self.get('password_hash', '')

    @password_hash.setter
    def password_hash(self, value):
        self['password_hash'] = value

    @property
    def cards(self):
        return self.get('cards', [])

    @cards.setter
    def cards(self, value):
        """
        just cards
        """
        self['cards'] = value

    @property
    def is_admin(self):
        # better via .get() in case the player is not updated yet
        return self.get('is_admin', False)

    @is_admin.setter
    def is_admin(self, value):
        self['is_admin'] = value
        self.save()

    @property
    def allows_spectators(self):
        # better via .get() in case the player is not updated yet
        # defaults to True
        return self.get('allows_spectators', True)

    @allows_spectators.setter
    def allows_spectators(self, value):
        self['allows_spectators'] = value
        self.save()

    @property
    def is_spectator_only(self):
        # defaults to False as most players want to play
        return self.get('is_spectator_only', False)

    @is_spectator_only.setter
    def is_spectator_only(self, value):
        self['is_spectator_only'] = value
        self.save()

    @property
    def table(self):
        return self['table']

    @table.setter
    def table(self, value):
        self['table'] = value
        self.save()

    @property
    def eichel_ober_count(self):
        return self.get('eichel_ober_count', 0)

    @eichel_ober_count.setter
    def eichel_ober_count(self, value):
        self['eichel_ober_count'] = value

    @property
    def exchange_peer_id(self):
        return self.get('exchange_peer_id', '')

    @exchange_peer_id.setter
    def exchange_peer_id(self, value):
        self['exchange_peer_id'] = value

    @property
    def is_playing(self):
        """
        double-check if player sits at some table - make sure it can be deleted
        """
        for table in self.game.tables.values():
            if self.id in table.players:
                # just in case the table was not stored yet
                self.table = table.id
                return True
        return False

    @property
    def tricks(self):
        """
        return current tricks of player, e.g. for displaying then at score dialog
        """
        tricks = []
        if self.is_playing:
            for trick in [x for x in self.game.tables[self.table].round.tricks.values() if x.owner == self.id]:
                tricks.append(trick)
        return tricks

    def get_id(self):
        """
        for Flask load user mechanism - has to be overloading
        """
        return self.id

    def set_password(self, password):
        """
        create hash of given password
        """
        self.password_hash = generate_password_hash(password)
        self.save()

    def check_password(self, password):
        """
        compare hashed password with given one
        """
        return check_password_hash(self.password_hash, password)

    def get_cards(self):
        """
        give complete card objects to player to be displayed in browser
        if player is idle just remove remaining cards from previous session
        """
        cards = []
        if self.table in self.game.tables:
            if self.id not in self.game.tables[self.table].players_idle:
                try:
                    for card_id in self.cards:
                        cards.append(Deck.cards[card_id])
                except KeyError as error:
                    # cards might have been here from debugging or an earlier game - just reset them
                    cards = []
                    self.cards = cards
            else:
                self.cards = cards
        return cards

    def remove_card(self, card_id):
        """
        remove card after having played it
        """
        self.cards.pop(self.cards.index(card_id))
        self.save()

    def remove_cards(self, card_ids):
        """
        remove multiple cards during exchange
        """
        for card_id in card_ids:
            if card_id in self.cards:
                self.cards.pop(self.cards.index(card_id))
        self.save()

    def remove_all_cards(self):
        """
        if player is idle or gets new cards it doesn't need its old cards
        """
        self.cards.clear()
        self.save()

    def exchange_new(self, peer_id):
        """
        start new exchange process
        """
        self.exchange_peer_id = peer_id
        self.save()

    def exchange_clear(self):
        """
        remove obsolete exchange peer
        """
        self.exchange_peer_id = ''
        self.save()



class Trick(Document3000):
    """
    contains all players and cards of moves - always 4
    2 synchronized lists, players and cards, should be enough to be indexed
    """

    def __init__(self, trick_id='', document=None, game=None):
        self.game = game
        if trick_id:
            # ID generated from Round object
            self['_id'] = f'trick-{trick_id}'
            super().__init__(database=self.game.db.database)
            self['type'] = 'trick'
            # initialize
            self.reset()
        elif document:
            super().__init__(database=self.game.db.database, document_id=document['_id'])
            # get document data from document
            self.update(document)

    def __len__(self):
        return len(self['players'])

    @property
    def players(self):
        return self['players']

    @property
    def cards(self):
        return self['cards']

    @property
    def owner(self):
        return self['owner']

    @owner.setter
    def owner(self, value):
        self['owner'] = value
        self.save()

    @property
    def is_last_turn(self):
        if len(self) > 3:
            return True
        else:
            return False

    def reset(self):
        self['players'] = []
        self['cards'] = []
        # owner of the trick
        self['owner'] = False
        self.save()

    def add_turn(self, player_id, card_id):
        """
        when player plays card it will be added
        player_name is enough here but card object is needed, at least for getting card value
        """
        self.players.append(player_id)
        self.cards.append(card_id)
        self.save()

    def get_turn(self, turn_number):
        """
        return indexed turn - count does not start from 0 as the aren't in the real game neither
        """
        if 1 <= turn_number <= 4 and len(self.players) <= turn_number and len(self.cards) <= turn_number:
            return self.players[turn_number - 1], self.cards[turn_number - 1]
        else:
            return

    def get_cards(self):
        """
        give complete card objects to table to be displayed in browser
        """
        cards = []
        for card_id in self.cards:
            cards.append(Deck.cards[card_id])
        return cards


class Round(Document3000):
    """
    eternal round, part of a table
    """

    def __init__(self, players=[], game=None, round_id='', document=None):
        """
        either initialize new round or load it from CouchDB
        """
        self.game = game
        # collection of tricks per round - its number should not exceed cards_per_player
        self.tricks = {}
        if round_id:
            # ID for CouchDB - comes already quoted from table
            self['_id'] = f'round-{round_id}'
            super().__init__(database=self.game.db.database)
            # type is for CouchDB
            self['type'] = 'round'
            # what table?
            self['id'] = round_id
            # list of the 4 players in round
            self['players'] = []
            # keep track of turns in round
            self['turn_count'] = 0
            # ID of player which has current turn
            self['current_player'] = ''
            # as default play without '9'-cards
            # should be a property of table but rounds are initialized before tables and this leads to a logical
            # problem some lines later when cards are initialized and there are no tables yet which can be asked
            # for a .with_9 property
            self['with_9'] = False
            # even if not logical too just keep the undo setting here too to keep the table/round-settings together
            self['allow_undo'] = True
            self['allow_exchange'] = True
            # timestamp as checksum to avoid mess on client side if new cards are dealed
            # every deal gets its own timestamp to make cards belonging together
            self['cards_timestamp'] = 0
            # statistics of current round
            self['stats'] = {'score': {},
                             'tricks': {}}
            # cards shown by any player - if any cards are shown it contains the cards showing player_id
            self['player_showing_hand'] = False
            # store exchange data in extra sub-dict - defaults to empty, filled by .create_exchange()
            self['exchange'] = {}
            # initialize
            self.reset(players=players)
        elif document:
            super().__init__(database=self.game.db.database, document_id=document['_id'])
            # get data from given document
            self.update(document)
            # a new card deck for every round
            # decide if the '9'-cards are needed and do not give them to round if not
            if self.with_9:
                self.cards = list(Deck.cards)
            else:
                self.cards = [x.id for x in Deck.cards.values() if x.rank != 'Neun']
            # cards per player depend on playing with '9'-cards or not
            self.cards_per_player = len(self.cards) // 4

        # id migration fix - prepend "player-"
        # pretty silly but pragmatical, because the user base might be pretty small still
        # so no big problems are to be expected
        # no extra .save() needed because the next one will happen soon
        self.players = [f'player-{x}' if not x.startswith('player-') else x for x in self.players]
        if self.trick_order:
            self.trick_order = [f'player-{x}' if not x.startswith('player-') else x for x in self.trick_order]
        self.stats['score'] = {(f'player-{x}' if not x.startswith('player-') else x): y for (x, y) in
                               self.stats['score'].items()}
        self.stats['tricks'] = {(f'player-{x}' if not x.startswith('player-') else x): y for (x, y) in
                                self.stats['tricks'].items()}

        # just make sure tricks exist
        # + 1 due to range counting behaviour
        # no matter if '9'-cards are used just create database entries for all 12 possible tricks
        for trick_number in range(1, 13):
            trick = self.game.tricks.get(f'{self.id}-{trick_number}')
            if trick is None:
                # create trick in CouchDB if it does not exist yet
                self.game.tricks[f'{self.id}-{trick_number}'] = Trick(trick_id=f'{self.id}-{trick_number}',
                                                                      game=self.game)
            # access tricks per trick_count number, not as index starting from 0
            self.tricks[trick_number] = self.game.tricks[f'{self.id}-{trick_number}']

    @property
    def id(self):
        return self.get('id', '')

    @property
    def players(self):
        return self.get('players', [])

    @players.setter
    def players(self, value):
        self['players'] = value

    @property
    def turn_count(self):
        return self.get('turn_count', 0)

    @property
    def current_player_id(self):
        return self.get('current_player', '')

    @current_player_id.setter
    def current_player_id(self, value):
        self['current_player'] = value

    @property
    def with_9(self):
        # better via .get() in case the table is not updated yet
        return self.get('with_9', False)

    @with_9.setter
    def with_9(self, value):
        if type(value) == bool:
            self['with_9'] = value
        else:
            self['with_9'] = False
        self.save()

    @turn_count.setter
    def turn_count(self, value):
        self['turn_count'] = value

    @property
    def trick_order(self):
        return self.get('trick_order', [])

    @trick_order.setter
    def trick_order(self, value):
        self['trick_order'] = value

    @property
    def allow_undo(self):
        # better via .get() in case the table is not updated yet
        return self.get('allow_undo', True)

    @allow_undo.setter
    def allow_undo(self, value):
        if type(value) == bool:
            self['allow_undo'] = value
        else:
            self['allow_undo'] = False
        self.save()

    @property
    def allow_exchange(self):
        # better via .get() in case the table is not updated yet
        return self.get('allow_exchange', True)

    @allow_exchange.setter
    def allow_exchange(self, value):
        if type(value) == bool:
            self['allow_exchange'] = value
        else:
            self['allow_exchange'] = False
        self.save()

    @property
    def exchange(self):
        return self.get('exchange', {})

    @exchange.setter
    def exchange(self, value):
        self['exchange'] = value

    @property
    def trick_count(self):
        # just count tricks which already have an owner - this is the number of already played tricks
        return len([x for x in self.tricks.values() if x.owner])

    @property
    def cards_timestamp(self):
        # no setter available, will be set by calculate_cards_timestamp()
        if not self.get('cards_timestamp'):
            self.calculate_cards_timestamp()
            self.save()
        return self['cards_timestamp']

    @property
    def stats(self):
        if not self.get('stats'):
            # stats dicts have to be created, not just returned as empty dicts
            self['stats'] = {'score': {},
                             'tricks': {}}
        return self['stats']

    @property
    def player_showing_hand(self):
        return self.get('player_showing_hand', False)

    @player_showing_hand.setter
    def player_showing_hand(self, value):
        self['player_showing_hand'] = value

    @property
    def current_trick(self):
        """
        enable access to current trick
        current trick is always ahead of trick count, because the latter counts the done tricks
        """
        return self.tricks.get(self.trick_count + 1)

    @property
    def previous_trick(self):
        """
        return previous trick to enable reclaiming
        trick count counts the done tricks so the previous trick has the index of tricḱ_count
        """
        return self.tricks.get(self.trick_count)

    @property
    def played_cards(self):
        """
        return list of all cards played in this round
        """
        played_cards = []
        for trick in self.tricks.values():
            for card in trick.cards:
                played_cards.append(card)
        return played_cards

    @property
    def needs_dealing(self):
        """
        returns information if dealing is needed because the round begins
        """
        # if no card was played yet we might need some cards
        return self.turn_count == 0 and len(self.players) == 4

    @property
    def needs_trick_claiming(self):
        """
        returns information if there is need for the claim trick button
        """
        return self.turn_count % 4 == 0 and \
               self.turn_count > 0 and \
               not self.is_finished

    @property
    def card_played(self):
        """
        info if any card has been played already
        """
        return self.turn_count > 0

    @property
    def is_finished(self):
        """
        check if round is over - reached when all cards are played
        """
        # count number of already played cards
        played_cards = []
        # pick tricks with already played cards
        for trick in [x for x in self.tricks.values() if len(x.cards) > 0]:
            played_cards += trick.cards
        # just return if all cards are played or not
        return len(played_cards) == len(self.cards)

    @property
    def is_reset(self):
        """
        check if round has been freshly reset
        """
        return self.turn_count == 0

    def reset(self, players=[]):
        """
        used by __init__ and by table at start of a new round
        """
        # if more than 4 players they change for every round
        # changing too because of the position of player changes with every round
        self.players = players

        # counting all turns
        self.turn_count = 0

        # at the beginning of course no card is shown
        self.player_showing_hand = False

        # at start there is no exchange
        self.reset_exchange()

        # tricks have to be reset too when round is reset
        for trick in self.tricks.values():
            if trick is not None:
                trick.reset()
        # dynamic order, depending on who gets tricks
        self.trick_order = []

        # current player - starts with the one following the dealer - only possible if there are at least 2
        if self.players and len(self.players) > 1:
            self.current_player_id = self.players[1]
        else:
            self.current_player_id = None

        # needed for player HUD
        self.calculate_trick_order()

        # reset score and tricks
        self.calculate_stats()

        # a new card deck for every round
        # decide if the '9'-cards are needed and do not give them to round if not
        if self.with_9:
            self.cards = list(Deck.cards)
        else:
            self.cards = [x.id for x in Deck.cards.values() if x.rank != 'Neun']
        # cards per player depend on playing with '9'-cards or not
        self.cards_per_player = len(self.cards) // 4

        # first shuffling...
        self.shuffle()
        # ...then dealing
        self.deal()

        # avoid multiple time-consuming .save(), concentrating them here
        for player_id in self.players:
            self.game.players[player_id].save()

        self.save()

    def calculate_cards_timestamp(self):
        """
        store moment of shuffling for comparing cards when being sorted and freshly dealed at one time
        """
        self['cards_timestamp'] = int(time() * 100000)

    def shuffle(self):
        """
        shuffle cards
        """
        # very important for game - some randomness
        seed()
        shuffle(self.cards)
        self.calculate_cards_timestamp()

    def deal(self):
        """
        deal cards, will be saved by .reset()
        """
        # simple counter to deal cards to all players
        player_count = 0
        for player_id in self.players:
            player = self.game.players[player_id]
            # reset counter for Eichel Ober cards
            player.eichel_ober_count = 0
            for card_id in range(self.cards_per_player):
                # cards are given to players, segmented by range
                player.cards = self.cards[player_count * self.cards_per_player:
                                          player_count * self.cards_per_player +
                                          self.cards_per_player]
            # raise counter for Eichel Ober cards if player has one or two
            for card_id in player.cards:
                if Deck.cards[card_id].name == 'Eichel-Ober':
                    player.eichel_ober_count += 1

            # next player
            player_count += 1

    def take_trick(self, player_id):
        """
        set player as owner of current trick
        """
        # trick_count + 1 is the current trick which will be taken
        self.game.tricks[f'{self.id}-{self.trick_count + 1}'].owner = player_id
        self.current_player_id = player_id
        self.save()

    def get_current_player_id(self):
        """
        get player for next turn
        """
        current_player_id_index = self.players.index(self.current_player_id)
        if current_player_id_index < 3:
            # set new current player
            self.current_player_id = self.players[current_player_id_index + 1]
        else:
            self.current_player_id = self.players[0]
        self.save()
        # current player is the next player
        return self.current_player_id


    def create_exchange(self, player1_id, player2_id):
        """
        opens exchange for 2 players
        """
        # force alphabetical order of exchange hash to avoid 2 exchanges of same players vice versa
        self.exchange[get_hash(player1_id, player2_id)] = {player1_id: [],
                                                           player2_id: []}
        self.save()
        return True

    def update_exchange(self, player_id, cards_ids):
        """
        modify exchange during players are dragging and dropping cards
        """
        player = self.game.players[player_id]
        exchange_hash = get_hash(player.id, player.exchange_peer_id)
        if exchange_hash in self.exchange and \
                player_id in self.exchange[exchange_hash]:
            self.exchange[exchange_hash][player.id] = cards_ids
            self.save()
            return True
        return False

    def reset_exchange(self):
        """
        used to remove all open exchanges, for example at .reset()
        """
        self.exchange = {}

    def is_exchange_needed(self, player_id):
        """
        check if there are ongoing exchanges where player is involved
        """
        player = self.game.players[player_id]
        exchange_hash = get_hash(player.id, player.exchange_peer_id)
        if exchange_hash in self.exchange and player.id in self.exchange[exchange_hash]:
            # if player did not change anything echange is needed
            if not self.exchange[exchange_hash][player.id]:
                return True
            # find out if any exchange peer member already has cards
            for member_id in self.exchange[exchange_hash]:
                if len(self.exchange[exchange_hash][member_id]) > 0:
                    break
            else:
                # if both exchange peers did not exchange any card yet exchange is needed
                return True
            # find out if the cards this player wants to exchange already found their way to its peer
            if not all(x in self.game.players[player.exchange_peer_id].cards for x in self.exchange[exchange_hash][player.id]):
                return True
        return False

    def calculate_stats(self):
        """
        get score and tricks count of players for display
        """
        score = {}
        tricks = {}
        for player_id in self.players:
            score[player_id] = 0
            tricks[player_id] = 0
        for trick in self.tricks.values():
            if trick and trick.owner:
                if trick.owner not in score:
                    score[trick.owner] = 0
                # add score of trick deck cards to owner score
                for card_id in trick.cards:
                    score[trick.owner] += Deck.cards[card_id].value
                if trick.owner not in tricks:
                    tricks[trick.owner] = 0
                # add number of tricks count to owner
                tricks[trick.owner] += 1
        self.stats['score'] = deepcopy(score)
        self.stats['tricks'] = deepcopy(tricks)

    def calculate_trick_order(self):
        """
        get order by arranging players list starting from current player who is first in this trick
        """
        if self.current_player_id:
            current_player_id_index = self.players.index(self.current_player_id)
            self.trick_order = self.players[current_player_id_index:] + self.players[:current_player_id_index]

    def increase_turn_count(self):
        self.turn_count += 1
        self.save()

    def get_players_shuffled_cards(self):
        """
        retrieve all cards of all players for spectator mode
        """
        players_cards = []
        for player_id in self.players:
            # only if player allows it
            if self.game.players[player_id].allows_spectators:
                # players_cards.append(shuffle(self.game.players[player_id].get_cards()))
                cards = self.game.players[player_id].get_cards()
                shuffle(cards)
                players_cards.append(cards)
            else:
                players_cards.append([])
        return players_cards

    def undo(self):
        """
        undo last trick by request
        """
        # if already some tricks exist take first player as it started the trick
        if self.current_trick.players:
            for player_id, card_id in zip(self.current_trick.players, self.current_trick.cards):
                self.game.players[player_id].cards.append(card_id)
                # decrease turn_count here to avoid extra self.save() like in increase_turn_count()
                self.turn_count -= 1
            self.current_player_id = self.current_trick.players[0]
            self.current_trick.reset()
        # otherwise the previous trick is to be treated
        else:
            for player_id, card_id in zip(self.previous_trick.players, self.previous_trick.cards):
                self.game.players[player_id].cards.append(card_id)
                # decrease turn_count here to avoid extra self.save() like in increase_turn_count()
                self.turn_count -= 1
            self.current_player_id = self.previous_trick.players[0]
            self.previous_trick.reset()
        # trick order has to be fixed
        self.calculate_trick_order()
        # recalculate statistics due to reverted ownerships
        self.calculate_stats()
        # finally save undone trick
        self.save()


class Table(Document3000):
    """
    Definition of a table used by group of players
    """

    def __init__(self, name='', document=None, game=None):
        # access to global game
        self.game = game
        if name:
            self['_id'] = self.game.create_table_id()
            super().__init__(database=self.game.db.database)
            # type is for CouchDB
            self['type'] = 'table'
            # what table?
            self['name'] = name
            # sync starts with 1
            self['sync_count'] = 1
            # default empty
            # quite likely order is about to vanish
            self['order'] = []
            self['players'] = []
            self['players_ready'] = []
            self['locked'] = False
            self['is_debugging'] = False
        elif document:
            super().__init__(database=self.game.db.database, document_id=document['_id'])
            # get data from given document
            self.update(document)
        # id migration fix - prepend "player-"
        # pretty silly but pragmatical, because the user base might be pretty small still
        # so no big problems are to be expected
        # no extra .save() needed because the next one will happen soon
        self.players = [f'player-{x}' if not x.startswith('player-') else x for x in self.players]
        self.order = [f'player-{x}' if not x.startswith('player-') else x for x in self.order]
        # yes, table_idmaster
        if self.id not in self.game.rounds:
            self.add_round()

    @property
    def id(self):
        # meanwhile returns CouchDB ID
        # return self.get('_id').replace('table-', '')
        return self.get('_id')

    @property
    def name(self):
        # legacy move for older tables which do not have names yet
        name = self.get('name')
        if not name:
            return self.id
        else:
            return name

    @property
    def order(self):
        return self['order']

    @order.setter
    def order(self, value):
        self['order'] = value

    @property
    def round(self):
        return self.game.rounds[self.id]

    @round.setter
    def round(self, value):
        self.game.rounds[self.id] = value

    @property
    def players(self):
        return self['players']

    @players.setter
    def players(self, value):
        self['players'] = value

    @property
    def players_ready(self):
        return self['players_ready']

    @players_ready.setter
    def players_ready(self, value):
        self['players_ready'] = value

    @property
    def players_json(self):
        """
        needed for data-* in HTML for JS
        """
        return dumps(self['players'])

    @property
    def players_active(self):
        """
        access all players willing to play
        """
        return [x for x in self['players'] if not self.game.players[x].is_spectator_only]

    @property
    def players_spectator_only(self):
        """
        all players which are only watching
        """
        return [x for x in self['players'] if self.game.players[x].is_spectator_only]

    @property
    def players_idle(self):
        """
        players who have to wait until round is over - all which are more than 4
        additionally those who are specators only
        """
        return self.order[4:]

    @property
    def locked(self):
        # better via .get() in case the table is not updated yet
        return self.get('locked', False)

    @locked.setter
    def locked(self, value):
        if type(value) == bool:
            self['locked'] = value
        else:
            self['locked'] = False
        self.save()

    @property
    def dealer(self):
        """
        give current dealer for next round back
        """
        if self.order:
            return self.order[0]
        else:
            return False

    @property
    def sync_count(self):
        """
        help to stabilize client synchronization
        """
        # backward compatibility
        if not self.get('sync_count'):
            self.reset_sync_count()
        return self['sync_count']

    @sync_count.setter
    def sync_count(self, value):
        self['sync_count'] = value

    @property
    def is_debugging(self):
        """
        flag showing if debugging is enabled or not
        """
        return self.get('is_debugging', False)

    @is_debugging.setter
    def is_debugging(self, value):
        if type(value) == bool:
            self['is_debugging'] = value
        else:
            self['is_debugging'] = False
        self.save()

    @property
    def needs_welcome(self):
        if len(self.players) < 4:
            return True
        else:
            return False

    def increase_sync_count(self):
        """
        to be called after various actions
        """
        self['sync_count'] += 1
        # just return new sync count to have it ready for use
        return self['sync_count']

    def reset_sync_count(self):
        """
        initial count
        """
        self['sync_count'] = 0

    def add_player(self, player_id):
        """
        adding just one player to the party
        """
        if player_id not in self.players:
            self.players.append(player_id)
            # only a real player makes sense to be listed in order
            if not self.game.players[player_id].is_spectator_only:
                self.order.append(player_id)
            self.save()
        # remove old remains of previous table
        if self.game.players[player_id].table != self.id:
            table = self.game.players[player_id].table
            if table in self.game.tables:
                self.game.tables[table].remove_player(player_id)
        # clean player cards if being idle
        if player_id in self.players_idle:
            self.game.players[player_id].remove_all_cards()
        # store table in player too
        self.game.players[player_id].table = self.id

    def remove_player(self, player_id):
        """
        remove player - mostly if entering another table
        """
        # make sure really no trace of player sticks somewhere
        while player_id in self.players:
            self.players.pop(self.players.index(player_id))
        while player_id in self.order:
            self.order.pop(self.order.index(player_id))
        while player_id in self.round.players:
            self.round.players.pop(self.round.players.index(player_id))
        while player_id in self.round.trick_order:
            self.round.trick_order.pop(self.round.trick_order.index(player_id))
        if self.round.current_player_id == player_id:
            self.round.current_player_id == ''
        self.game.players[player_id].table = ''
        if player_id not in self.players and \
                player_id not in self.order and \
                player_id not in self.round.players and \
                player_id not in self.round.trick_order:
            self.round.save()
            self.save()
            self.game.players[player_id].save()
            return True

    def add_round(self):
        """
        only 4 players can play at once - find out who and start a new round
        """
        if self.order:
            players = self.order[:4]
        else:
            players = []
        self.round = Round(players=players, round_id=self.id, game=self.game)
        self.save()

    def reset_round(self):
        """
        reset round either when starting a new round on table or when restarting during game
        """
        if self.order:
            players = self.order[:4]
        else:
            players = []
        self.round.reset(players=players)
        self.reset_ready_players()
        self.increase_sync_count()
        self.save()

    def start(self):
        """
        completely new start from setup dialog
        """
        # reset ready players
        self.players_ready = []
        # beginning order is the same like players without spectators
        self.order = self.players_active[:]
        # new sync count
        self.reset_sync_count()
        # new round of 4 players
        self.reset_round()

    def shift_players(self):
        """
        last dealer is moved to the end of the players list
        spectators get glued at the end to avoid them appearing out of nothing
        """
        self.players = self.players_active[1:] + self.players_active[:1] + self.players_spectator_only
        self.order = self.players_active[:]
        # self.order = self.order[1:] + self.order[:1]
        self.save()

    def add_ready_player(self, player_id):
        """
        organize players who are ready for the next round in a list
        """
        if player_id not in self.players_ready:
            self.players_ready.append(player_id)

    def reset_ready_players(self):
        """
        reset list of ready players in cases they are about to be collected, e.g. when requesting a round reset
        """
        self.players_ready = []
        self.save()

    def show_hand(self, player):
        """
        show cards of player on table
        """
        self.round.player_showing_hand = player.id
        self.increase_sync_count()

    def log(*args):
        """
        very poor logging
        """
        print(args)


class Game:
    """
    organizes tables
    """

    def __init__(self, db=None):
        """
        access to game DB and cards deck
        """
        self.db = db
        self.deck = Deck()
        # load game objects from CouchDB
        self.load_from_db()

    @property
    def needs_welcome(self):
        """
        checks if there is no table - if so, then show welcome message
        """
        if len(self.tables) == 0:
            return True
        else:
            return False

    def load_from_db(self):
        """
        initialize all game components like tables and players
        """
        # get players from CouchDB
        self.players = {}
        for player_id, document in self.db.filter_by_type_real_id('player').items():
            self.players[player_id] = Player(document=document, game=self)

        # if no player exists create a dummy admin account
        if len(self.players) == 0:
            self.add_player(name='admin',
                            password='admin',
                            is_admin=True,
                            is_spectator_only=True,
                            allows_spectators=True)

        # all tricks belonging to certain rounds shall stay in CouchDB too
        self.tricks = {}
        for trick_id, document in self.db.filter_by_type_as_number('trick').items():
            self.tricks[trick_id] = Trick(document=document, game=self)

        # get rounds from CouchDB
        self.rounds = {}
        # for round_id, document in self.db.filter_by_type_as_number('round').items():
        for round_id, document in self.db.filter_by_type_as_number('round').items():
            self.rounds[round_id] = Round(document=document, game=self)

        # store tables
        self.tables = {}
        for table_id, document in self.db.filter_by_type_real_id('table').items():
            self.tables[table_id] = Table(document=document, game=self)

        # remove legacy URL-encoded IDs
        self.cleanup_ids()

        # check for locked tables
        self.check_tables()

    def add_player(self, name='', password='', is_spectator_only=False, allows_spectators=False, is_admin=False,
                   convert=False):
        """
        adds a new player
        """
        if name:
            if name not in [x.name for x in self.players.values()] or convert:
                player = Player(name=name, game=self)
                self.players[player.id] = player
                if password:
                    self.players[player.id].set_password(password)
                if is_admin:
                    self.players[player.id].is_admin = True
                self.players[player.id].is_spectator_only = is_spectator_only
                self.players[player.id].allows_spectators = allows_spectators
                # return player object to get its ID for example
                return player
        # when no name was given
        return False

    def add_table(self, name='', convert=False):
        """
        adds a new table (to sit and play on, no database table!)
        """
        if name:
            if name not in [x.name for x in self.tables.values()] or convert:
                table = Table(name=name, game=self)
                self.tables[table.id] = table
                # return table object to get its ID for example
                return table
        # when no name was given
        return False

    def delete_player(self, player_id):
        """
        remove all traces of a player which is going to be deleted
        """
        for table in self.tables.values():
            if player_id in table.players:
                table.players.pop(table.players.index(player_id))
                table.save()
            if player_id in table.order:
                table.order.pop(table.order.index(player_id))
                table.save()
        for round in self.rounds.values():
            if player_id in round.players:
                round.players.pop(round.players.index(player_id))
                round.save()
            if player_id in round.trick_order:
                round.trick_order.pop(round.trick_order.index(player_id))
                round.save()
        if player_id in self.players:
            self.players[player_id].delete()
            self.players.pop(player_id)
            return True
        return False

    def get_player(self, name):
        """
        check if player with this name already exists
        """
        # filter players
        players_list = [x for x in self.players.values() if x.name == name]
        if len(players_list) == 1:
            return players_list[0]
        return False

    def get_table(self, name):
        """
        check if table with this name already exists
        """
        # filter tables
        tables_list = [x for x in self.tables.values() if x.name == name]
        if len(tables_list) == 1:
            return tables_list[0]
        return False

    def delete_table(self, table_id):
        """
        remove all traces of a table and its round
        """
        table = self.tables.get(table_id)
        if table and \
                len(table.players) == 0:
            for player in self.players.values():
                if player.table == table_id:
                    player.table = ''
            if table_id in self.rounds:
                for trick_number in self.rounds[table_id].tricks:
                    trick_id = f'{table_id}-{trick_number}'
                    if trick_id in self.tricks:
                        self.tricks[trick_id].delete()
                        self.tricks.pop(trick_id)
                self.rounds[table_id].delete()
                self.rounds.pop(table_id)
            if table_id in self.tables:
                self.tables[table_id].delete()
                self.tables.pop(table_id)
            for trick in range(1, 13):
                if f'trick-{table_id}-{trick}' in self.tricks:
                    self.tricks[f'trick-{table_id}-{trick}'].delete()
                    self.tricks.pop(f'trick-{table_id}-{trick}')
            return True
        else:
            return False

    def check_tables(self):
        """
        check if any formerly locked table is now emtpy and should be unlocked
        """
        for table in self.tables.values():
            if table.locked and len(table.players) == 0:
                table.locked = False

    def create_player_id(self):
        """
        creates id for player and checks if it already exists
        """
        player_id = 1
        while f'player-{player_id}' in self.players:
            player_id += 1
        return f'player-{player_id}'

    def create_table_id(self):
        """
        creates id for table and checks if it already exists
        """
        table_id = 1
        while f'table-{table_id}' in self.tables:
            table_id += 1
        return f'table-{str(table_id)}'

    def cleanup_ids(self):
        """
        find and remove old URL-encoded IDs, kick out
        """
        # first collect all legacy players...
        for player in list(self.players.values()):
            if '%' in player.id:
                # kick it out
                self.delete_player(player.id)
        # ...and tables
        for table in list(self.tables.values()):
            if '%' in table.id:
                # remove all players to make table deletable
                table.players = table.order = table.round.players = []
                # kick it out
                self.delete_table(table.id)
            else:
                for players in [table['players'], table['order'], table.round['players']]:
                    for player in list(players):
                        if not player in self.players:
                            players.remove(player)
