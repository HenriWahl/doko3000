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
               # 'Herz',
               # 'Grün',
               'Eichel')
    RANKS = {'Zehn': 10,
             # 'Unter': 2,
             # 'Ober': 3,
             # 'König': 4,
             'Ass': 11}
    NUMBER = 2 # Doppelkopf :-)!
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

    @property
    def cards(self):
        return self['cards']

    @property
    def left(self):
        return self['left']

    @left.setter
    def left(self, value):
        self['left'] = value
        self.save()

    @property
    def right(self):
        return self['right']

    @right.setter
    def right(self, value):
        self['right'] = value
        self.save()

    @property
    def opposite(self):
        return self['opposite']

    @opposite.setter
    def opposite(self, value):
        self['opposite'] = value
        self.save()

    def set_password(self, password):
        """
        create hash of given password
        """
        self['password_hash'] = generate_password_hash(password)
        self.save()

    def check_password(self, password):
        """
        compare hashed password with given one
        """
        return check_password_hash(self.password_hash, password)

    def add_card(self, card):
        self['cards'].append(card)

    def get_cards(self):
        """
        give complete card objects to player to be displayed in browser
        """
        cards = []
        for card_id in self['cards']:
            cards.append(Deck.cards[card_id])
        return cards

    def remove_all_cards(self):
        self['cards'] = []


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
            # self['players'] = []
            # self['cards'] = []
            # # owner of the trick
            # self['owner'] = False
            # self.save()
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
    def owner(self, player_id):
        self['owner'] = player_id
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
        self['players'].append(player_id)
        self['cards'].append(card_id)

    def get_turn(self, turn_number):
        """
        return indexed turn - count does not start from 0 as the aren't in the real game neither
        """
        if 1 <= turn_number <= 4 and len(self['players']) <= turn_number and len(self['cards']) <= turn_number:
            return self['players'][turn_number - 1], self['cards'][turn_number - 1]
        else:
            return

    def is_last_turn(self):
        if len(self) > 3:
            return True
        else:
            return False


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
        self.tricks = {}
        if round_id:
            # ID still name, going to be number - for CouchDB
            self['_id'] = f'round-{round_id}'
            Document.__init__(self, self.game.db.database)
            # type is for CouchDB
            self['type'] = 'round'
            # what table?
            self['id'] = round_id
            # # if more than 4 players they change for every round
            # # changing too because of the position of dealer changes with every round
            # self['players'] = players
            # # order is important - but might be obsolete
            # self['order'] = players
            # # collection of tricks per round - its number should not exceed cards_per_player
            # self['tricks'] = []
            # # counting all turns
            # self['turn_count'] = 0
            # # current player - starts with the one following the dealer
            # self['current_player'] = self['players'][1]
            # self.save()
            self.reset(players=players)
        elif document_id:
            Document.__init__(self, self.game.db.database, document_id=document_id)
            # get document data from CouchDB
            self.fetch()
            print(self)

        # # cards are an important part but makes in a round context only sense if shuffled
        # # not needed outside or in CouchDB
        # self.cards = list(Deck.cards)
        # # needed to know how many cards are dealed
        # # same as number of tricks in a round
        # self.cards_per_player = len(self.cards) // 4

        # send info to HUD displays on players tables
        #self.tell_players_about_opponents()
        # first shuffling...
        self.shuffle()
        # ...then dealing
        self.deal()


    @property
    def players(self):
        return self['players']

    @property
    def id(self):
        return self['id']

    # @property
    # def order(self):
    #     return self['order']

    # @property
    # def tricks(self):
    #     return self['tricks']

    @property
    def turn_count(self):
        return self['turn_count']

    @property
    def current_player(self):
        return self['current_player']

    @current_player.setter
    def current_player(self, new_current_player):
        self['current_player'] = new_current_player

    def reset(self, players=[]):
        """
        used by __init__ and by table at start of a new round
        """
        # if more than 4 players they change for every round
        # changing too because of the position of dealer changes with every round
        self['players'] = players
        # # order is important - but might be obsolete
        # self['order'] = players
        # collection of tricks per round - its number should not exceed cards_per_player
        #self['tricks'] = {}
        # for trick_number in range(self.cards_per_player):
        #     self.tricks[trick_number] = Trick(trick_id=)
        # + 1 due to range counting behaviour
        self.tricks = {}
        for trick_number in range(1, self.cards_per_player + 1):
            trick = self.game.tricks.get(f"{self['id']}-{trick_number}")
            if trick is None:
                self.game.tricks[f"{self['id']}-{trick_number}"] = Trick(trick_id=f"{self['id']}-{trick_number}",
                                                                      game=self.game)
            else:
                trick.reset()
            self.tricks[trick_number] = trick

        # counting all turns
        self['turn_count'] = 0

        # counting all tricks
        # starting with first trick number 1
        self['trick_count'] = 1

        # current player - starts with the one following the dealer
        if self['players']:
            self['current_player'] = self['players'][1]
        else:
            self['current_player'] = None

        self.calculate_opponents()

        self.cards = list(Deck.cards)
        # first shuffling...
        self.shuffle()
        # ...then dealing
        self.deal()
        self.save()

    def shuffle(self):
        """
        shuffle cards
        """
        shuffle(self.cards)
        pass

    def deal(self):
        """
        deal cards
        """
        for player_id in self['players']:
            self.game.players[player_id].remove_all_cards()
            for card in range(self.cards_per_player):
                # cards are given to players so the can be .pop()ed
                self.game.players[player_id].add_card(self.cards.pop())

    def add_trick(self, player_id):
        """
        set player as owner of current trick
        """
        # self['tricks'].append(Trick(game=self.game))
        self.game.tricks[f"{self.id}-{self['trick_count']}"].owner = player_id
        self.increase_trick_count()
        self['current_player'] = player_id

    @property
    def current_trick(self):
        """
        enable access to current trick
        """
        print(self.tricks)
        return self.tricks[self['trick_count']]

    @property
    def previous_trick(self):
        """
        return previous trick to enable reclaiming
        """
        return self.tricks[self['trick_count'] - 1]

    def get_next_player(self):
        """
        get player for next turn
        """

        current_player_index = self['players'].index(self['current_player'])

        if current_player_index < 3:
            # set new current player
            self['current_player'] = self['players'][current_player_index + 1]
        else:
            self['current_player'] = self['players'][0]
        # current player is the next player
        return self['current_player']

    def is_finished(self):
        """
        check if round is over - reached when all cards are played
        """
        print(len(Deck.cards), self['turn_count'])
        return len(Deck.cards) == self['turn_count']

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
        for player_id in self['players']:
            player_index = self['players'].index(player_id)
            player_order_view = copy(self['players'])
            for i in range(player_index):
                player_order_view.append(player_order_view.pop(0))
            self.game.players[player_id].left = player_order_view[1]
            self.game.players[player_id].opposite = player_order_view[2]
            self.game.players[player_id].right = player_order_view[3]

    def increase_turn_count(self):
        self['turn_count'] += 1
        self.save()

    def increase_trick_count(self):
        self['trick_count'] += 1
        print(self)
        self.save()
        pass


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
            #self['round'] = ''
            self['players'] = []
            self['players_ready'] = []
        elif document_id:
            Document.__init__(self, self.game.db.database, document_id=document_id)
            # get document data from CouchDB
            self.fetch()
            print(self)
        # either is not set yet or just a new table with new round
        # if self['round'] == '':
        #     self['round'] = self.new_round()
        # yes, table_id
        if not self['id'] in self.game.rounds:
            self.new_round()
        self.save()

    @property
    def order(self):
        return self['order']

    @order.setter
    def order(self, new_order):
        self['order'] = new_order

    @property
    def id(self):
        return self['id']

    @property
    def round(self):
        return self.game.rounds[self['id']]

    @round.setter
    def round(self, new_round):
        self.game.rounds[self['id']] = new_round

    @property
    def players(self):
        return self['players']

    @property
    def players_ready(self):
        return self['players_ready']

    def add_player(self, player_id):
        """
        adding just one player to the party
        """
        if player_id not in self['players']:
            self['players'].append(player_id)

    def new_round(self):
        """
        only 4 players can play at once - find out who and start a new round
        """
        if self['order']:
            players = self['order'][:4]
        else:
            players = []
        self.round = Round(players=players, round_id=self['id'], game=self.game)

    def reset_round(self):
        if self['order']:
            players = self['order'][:4]
        else:
            players = []
        self.round.reset(players=players)
        self.reset_ready_players()
        self.save()

    def shift_players(self):
        """
        last dealer is moved to the end of the players list
        """
        self['order'].append(self['order'].pop(0))
        self.save()

    def get_dealer(self):
        """
        give current dealer for next round back
        """
        return self['order'][0]

    def add_ready_player(self, player):
        """
        organize players who are ready for the next round in a list
        """
        self['players_ready'].append(player)

    def reset_ready_players(self):
        self['players_ready'] = []
        self.save()


class Game:
    """
    organizes tables
    """
    def __init__(self, db=None):
        # very important for game - some randomness
        seed()
        self.db = db

    def initialize_components(self):
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
        #game.tables['test'].order = ['test1', 'test2', 'test3', 'test4', 'test5']
        self.tables['test'].order = ['test1', 'test2', 'test3', 'test4', 'test5']
        self.tables['test'].save()
    #if 'test' not in game.rounds:
    #    game.tables['test'].new_round()

#
# def test_database():
#     for test_player in ('test1', 'test2', 'test3', 'test4', 'test5'):
#         if test_player not in db.filter_by_type('player'):
#             player = game.add_player(player_id=test_player)
#             player.set_password(test_player)
