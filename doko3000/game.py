# game logic part of doko3000

from copy import copy
from random import seed, \
    shuffle

from cloudant.document import Document
from flask_login import UserMixin
from werkzeug.security import check_password_hash, \
    generate_password_hash


#
# from . import db


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
    SYMBOLS = ('Schell',
               'Herz',
               'Grün',
               'Eichel')
    RANKS = {'Zehn': 10,
             'Unter': 2,
             'Ober': 3,
             'König': 4,
             'Ass': 11}
    NUMBER = 2  # Doppelkopf :-)!
    # NUMBER = 1 # Debugging
    cards = {}

    # counter for card IDs in deck
    card_id = 0

    for number in range(NUMBER):
        for symbol in SYMBOLS:
            for rank in RANKS.items():
                cards[card_id] = Card(symbol, rank, card_id)
                card_id += 1

    # for symbol in SYMBOLS[0:2]:
    #     for rank in RANKS.items():
    #         cards[card_id] = Card(symbol, rank, card_id)
    #         card_id += 1


class Player(UserMixin, Document):
    """
    one single player on a table

    due to CouchDB Document class everything is now a dictionary
    """

    def __init__(self, player_id='', document_id='', game=None):
        self.game = game
        if player_id:
            # ID still name, going to be number - for CouchDB
            self['_id'] = f'player-{player_id}'
            Document.__init__(self, self.game.db.database)
            # ID for flask-login
            self['id'] = player_id
            # type is for CouchDB
            self['type'] = 'player'
            # name of player - to become somewhat more natural
            self['name'] = player_id
            # password hash
            self['password_hash'] = ''
            # current set of cards
            self['cards'] = []
            # which table player sits on
            self['table'] = ''
            # has admin rights
            self['is_admin'] = False
            # other players to the left, opposite and right of table
            self['left'] = self['opposite'] = self['right'] = None
            self.save()
        elif document_id:
            Document.__init__(self, self.game.db.database, document_id=document_id)
            # get document data from CouchDB
            self.fetch()
            # id needed for flask-login
            self['id'] = self['_id'].split('player-', 1)[1]

    @property
    def id(self):
        return self['id']

    @property
    def name(self):
        return self['name']

    @property
    def password_hash(self):
        return self['password_hash']

    @password_hash.setter
    def password_hash(self, value):
        self['password_hash'] = value

    @property
    def cards(self):
        return self['cards']

    @cards.setter
    def cards(self, value):
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
    def table(self):
        return self['table']

    @table.setter
    def table(self, value):
        self['table'] = value

    @property
    def left(self):
        return self['left']

    @left.setter
    def left(self, value):
        self['left'] = value

    @property
    def right(self):
        return self['right']

    @right.setter
    def right(self, value):
        self['right'] = value

    @property
    def opposite(self):
        return self['opposite']

    @opposite.setter
    def opposite(self, value):
        self['opposite'] = value

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
        """
        cards = []
        for card_id in self.cards:
            cards.append(Deck.cards[card_id])
        return cards

    def remove_card(self, card_id):
        """
        remove card after having played it
        """
        self.cards.pop(self.cards.index(card_id))
        self.save()

    def remove_all_cards(self):
        self.cards = []
        self.save()


class Trick(Document):
    """
    contains all players and cards of moves - always 4
    2 synchronized lists, players and cards, should be enough to be indexed
    """

    def __init__(self, trick_id='', document_id='', game=None):
        self.game = game
        if trick_id:
            # ID generated from Round object
            self['_id'] = f'trick-{trick_id}'
            Document.__init__(self, self.game.db.database)
            self['type'] = 'trick'
            # initialize
            self.reset()
        elif document_id:
            Document.__init__(self, self.game.db.database, document_id=document_id)
            # get document data from CouchDB
            self.fetch()

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

    def is_last_turn(self):
        if len(self) > 3:
            return True
        else:
            return False

    def get_cards(self):
        """
        give complete card objects to table to be displayed in browser
        """
        cards = []
        for card_id in self.cards:
            cards.append(Deck.cards[card_id])
        return cards


class Round(Document):
    """
    eternal round, part of a table
    """
    def __init__(self, players=[], game=None, round_id='', document_id=''):
        self.game = game
        # cards are an important part but makes in a round context only sense if shuffled
        # not needed outside or in CouchDB
        self.cards = list(Deck.cards)
        # needed to know how many cards are dealed
        # same as number of tricks in a round
        self.cards_per_player = len(self.cards) // 4
        if round_id:
            # ID still name, going to be number - for CouchDB
            self['_id'] = f'round-{round_id}'
            Document.__init__(self, self.game.db.database)
            # type is for CouchDB
            self['type'] = 'round'
            # what table?
            self['id'] = round_id
            # initialize
            self.reset(players=players)
        elif document_id:
            Document.__init__(self, self.game.db.database, document_id=document_id)
            # get document data from CouchDB
            self.fetch()
            # first shuffling...
            #self.shuffle()
            # ...then dealing
            #self.deal()

        # collection of tricks per round - its number should not exceed cards_per_player
        self.tricks = {}
        # + 1 due to range counting behaviour
        for trick_number in range(1, self.cards_per_player + 1):
            trick = self.game.tricks.get(f'{self.id}-{trick_number}')
            if trick is None:
                # create trick in CouchDB if it does not exist yet
                self.game.tricks[f'{self.id}-{trick_number}'] = Trick(trick_id=f'{self.id}-{trick_number}',
                                                                      game=self.game)
            # else:
            #     trick.reset()
            # access tricks per trick_count number, not as index starting from 0
            self.tricks[trick_number] = trick

    @property
    def id(self):
        return self['id']

    @property
    def players(self):
        return self['players']

    @players.setter
    def players(self, value):
        self['players'] = value

    @property
    def turn_count(self):
        return self['turn_count']

    @turn_count.setter
    def turn_count(self, value):
        self['turn_count'] = value

    @property
    def trick_count(self):
        return self['trick_count']

    @trick_count.setter
    def trick_count(self, value):
        self['trick_count'] = value

    @property
    def current_player(self):
        return self['current_player']

    @current_player.setter
    def current_player(self, value):
        self['current_player'] = value

    @property
    def current_trick(self):
        """
        enable access to current trick
        """
        return self.tricks[self.trick_count]

    @property
    def previous_trick(self):
        """
        return previous trick to enable reclaiming
        """
        return self.tricks[self.trick_count - 1]

    def reset(self, players=[]):
        """
        used by __init__ and by table at start of a new round
        """
        # if more than 4 players they change for every round
        # changing too because of the position of dealer changes with every round
        self.players = players

        # counting all turns
        self.turn_count = 0

        # counting all tricks
        # starting with first trick number 1
        self.trick_count = 1
        # tricks have to be reset too when round is reset
        for trick in self.tricks.values():
            if trick is not None:
                trick.reset()

        # current player - starts with the one following the dealer
        if self.players:
            self.current_player = self.players[1]
        else:
            self.current_player = None

        self.calculate_opponents()

        self.cards = list(Deck.cards)
        # first shuffling...
        self.shuffle()
        # ...then dealing
        self.deal()

        # avoid multiple time-consuming .save(), concentrating them here
        for player_id in self.players:
            self.game.players[player_id].save()

        self.save()

    def shuffle(self):
        """
        shuffle cards
        """
        # very important for game - some randomness
        seed()
        shuffle(self.cards)

    def deal(self):
        """
        deal cards
        """
        for player_id in self.players:
            self.game.players[player_id].remove_all_cards()
            for card in range(self.cards_per_player):
                # cards are given to players so the can be .pop()ed
                self.game.players[player_id].cards.append(self.cards.pop())
            #self.game.players[player_id].save()
        # not needed, is saved by .reset()
        #self.save()

    def add_trick(self, player_id):
        """
        set player as owner of current trick
        """
        # self['tricks'].append(Trick(game=self.game))
        self.game.tricks[f'{self.id}-{self.trick_count}'].owner = player_id
        self.increase_trick_count()
        self.current_player = player_id
        self.save()

    def shift_players(self):
        """
        get player for next turn
        """
        current_player_index = self.players.index(self.current_player)
        if current_player_index < 3:
            # set new current player
            self.current_player = self.players[current_player_index + 1]
        else:
            self.current_player = self.players[0]
        self.save()
        # current player is the next player
        return self.current_player

    def is_finished(self):
        """
        check if round is over - reached when all cards are played
        """
        return len(Deck.cards) == self.turn_count

    def get_score(self):
        score = {}
        for trick in self.tricks.values():
            if trick.owner:
                if trick.owner not in score:
                    score[trick.owner] = 0
                for card_id in trick.cards:
                    score[trick.owner] += Deck.cards[card_id].value
        return score

    def calculate_opponents(self):
        """
        give players info about whom they are playing against - interesting for HUD display
        """
        for player_id in self.players:
            player_index = self.players.index(player_id)
            player_order_view = copy(self.players)
            for i in range(player_index):
                player_order_view.append(player_order_view.pop(0))
            self.game.players[player_id].left = player_order_view[1]
            self.game.players[player_id].opposite = player_order_view[2]
            self.game.players[player_id].right = player_order_view[3]
            #self.game.players[player_id].save()

    def increase_turn_count(self):
        self.turn_count += 1
        self.save()

    def increase_trick_count(self):
        self.trick_count += 1
        self.save()


class Table(Document):
    """
    Definition of a table used by group of players
    """

    def __init__(self, table_id='', document_id='', game=None):
        self.game = game
        if table_id:
            # ID still name, going to be number - for CouchDB
            self['_id'] = f'table-{table_id}'
            Document.__init__(self, self.game.db.database)
            # type is for CouchDB
            self['type'] = 'table'
            # what table?
            self['id'] = table_id
            # default empty
            self['order'] = []
            self['players'] = []
            self['players_ready'] = []
        elif document_id:
            Document.__init__(self, self.game.db.database, document_id=document_id)
            # get document data from CouchDB
            self.fetch()
        # yes, table_id
        if not self['id'] in self.game.rounds:
            self.new_round()
        self.save()

    @property
    def id(self):
        return self['id']

    @property
    def order(self):
        return self['order']

    @order.setter
    def order(self, value):
        self['order'] = value
        self.save()

    @property
    def id(self):
        return self['id']

    @property
    def round(self):
        return self.game.rounds[self.id]

    @round.setter
    def round(self, value):
        self.game.rounds[self.id] = value

    @property
    def players(self):
        return self['players']

    @property
    def players_ready(self):
        return self['players_ready']

    @players_ready.setter
    def players_ready(self, value):
        self['players_ready'] = value

    def add_player(self, player_id):
        """
        adding just one player to the party
        """
        if player_id not in self.players:
            self.players.append(player_id)
            self.save()

    def new_round(self):
        """
        only 4 players can play at once - find out who and start a new round
        """
        if self.order:
            players = self.order[:4]
        else:
            players = []
        self.round = Round(players=players, round_id=self.id, game=self.game)

    def reset_round(self):
        if self.order:
            players = self.order[:4]
        else:
            players = []
        self.round.reset(players=players)
        self.reset_ready_players()
        self.save()

    def shift_players(self):
        """
        last dealer is moved to the end of the players list
        """
        self.order.append(self.order.pop(0))
        self.save()

    def get_dealer(self):
        """
        give current dealer for next round back
        """
        return self.order[0]

    def add_ready_player(self, player):
        """
        organize players who are ready for the next round in a list
        """
        self.players_ready.append(player)
        self.save()

    def reset_ready_players(self):
        self.players_ready = []
        self.save()


class Game:
    """
    organizes tables
    """

    def __init__(self, db=None):

        self.db = db

    def load_from_db(self):
        """
        initialize all game components like tables and players
        """
        # get players from CouchDB
        self.players = {}
        for player_id, document in self.db.filter_by_type('player').items():
            self.players[player_id] = Player(document_id=document['_id'], game=self)

        # all tricks belonging to certain rounds shall stay in CouchDB too
        self.tricks = {}
        for trick_id, document in self.db.filter_by_type('trick').items():
            self.tricks[trick_id] = Trick(document_id=document['_id'], game=self)

        # get rounds from CouchDB
        self.rounds = {}
        for round_id, document in self.db.filter_by_type('round').items():
            self.rounds[round_id] = Round(document_id=document['_id'], game=self)

        # store tables
        self.tables = {}
        for table_id, document in self.db.filter_by_type('table').items():
            self.tables[table_id] = Table(document_id=document['_id'], game=self)

    def add_player(self, player_id='', document_id=''):
        """
        adds a new player
        """
        if player_id not in self.players:
            self.players[player_id] = Player(player_id=player_id, game=self)
        # else:
        #     self.players[player_id] = Player(document_id=document_id)
        return self.players[player_id]

    def add_table(self, table_id='', document_id=''):
        """
        adds a new table (to sit and play on, no database table!)
        """
        if table_id not in self.tables:
            self.tables[table_id] = Table(table_id=table_id, game=self)
        return self.tables[table_id]

    def has_tables(self):
        if len(self.tables) == 0:
            return False
        else:
            return True

    def get_tables(self):
        return self.tables.values()

    def get_tables_names(self):
        return list(self.tables.keys())

    def get_players(self):
        return self.players.values()

    def test_game(self):
        self.add_table('test')
        for player_id, document in self.db.filter_by_type('player').items():
            player = self.add_player(player_id, document_id=document['_id'])
            self.tables['test'].add_player(player.id)
        # game.tables['test'].order = ['test1', 'test2', 'test3', 'test4', 'test5']
        self.tables['test'].order = ['test1', 'test2', 'test3', 'test4', 'test5']
        self.tables['test'].save()
    # if 'test' not in game.rounds:
    #    game.tables['test'].new_round()

#
# def test_database():
#     for test_player in ('test1', 'test2', 'test3', 'test4', 'test5'):
#         if test_player not in db.filter_by_type('player'):
#             player = game.add_player(player_id=test_player)
#             player.set_password(test_player)
