# game logic part of doko3000

from copy import copy
from random import seed, \
    shuffle

from cloudant.document import Document
from flask_login import UserMixin
from werkzeug.security import check_password_hash, \
    generate_password_hash

from . import db


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
    """
    def __init__(self, player_id='', document_id='', **kwargs):
        if player_id:
            # ID still name, going to be number - for CouchDB
            self['_id'] = f'player-{player_id}'
            # ID for login
            self['id'] = player_id
            # type is for CouchDB
            self['type'] = 'player'
            # name of player
            self['name'] = player_id
            # password hash
            self['password_hash'] = ''
            # current set of cards
            self['cards'] = []
            # other players to the left, opposite and right of table
            self['left'] = self['opposite'] = self['right'] = None
        elif document_id:
            Document.__init__(self, db.database, document_id=document_id)
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

    @property
    def right(self):
        return self['right']

    @property
    def opposite(self):
        return self['opposite']

    # @cards.setter
    # def cards(self):
    #     return self['cards']

    def set_password(self, password):
        """
        create hash of given password
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """
        compare hashed password with given one
        """
        return check_password_hash(self.password_hash, password)

    def add_card(self, card):
        self.cards.append(card)

    def remove_all_cards(self):
        self['cards'] = []


class Trick:
    """
    contains all players and cards of moves - always 4
    2 synchronized lists, players and cards, should be enough to be indexed
    """
    def __init__(self):
        self.players = []
        self.cards = []
        # owner of the trick
        self.__owner = False

    def __len__(self):
        return len(self.players)

    def add_turn(self, player_name, card_id):
        """
        when player plays card it will be added
        player_name is enough here but card object is needed, at least for getting card value
        """
        self.players.append(player_name)
        self.cards.append(Deck.cards[card_id])

    def get_turn(self, turn_number):
        """
        return indexed turn - count does not start from 0 as the aren't in the real game neither
        """
        if 1 <= turn_number <= 4 and len(self.players) <= turn_number and len(self.cards) <= turn_number:
            return self.players[turn_number - 1], self.cards[turn_number - 1]
        else:
            return

    @property
    def owner(self):
        return self.__owner

    @owner.setter
    def owner(self, player):
        self.__owner = player

    def is_last_turn(self):
        if len(self) > 3:
            return True
        else:
            return False


class Round:
    """
    one round
    """
    def __init__(self, players):
        # if more than 4 players they change for every round
        # changing too because of the position of dealer changes with every round
        self.players = players
        self.players_id = [x.id for x in self.players.values()]
        # order is important - index 0 is the dealer
        self.order = list(players.values())

        self.tell_players_about_opponents()

        # # list of players as names for JSON serialization
        # self.order_names = [x.name for x in self.order]
        # cards are an important part but makes in a round context only sense if shuffled
        self.cards = list(Deck.cards.values())
        # needed to know how many cards are dealed
        # same as number of tricks in a round
        self.cards_per_player = len(self.cards) // len(self.players)
        # collection of tricks per round - its number should not exceed cards_per_player
        self.tricks = []
        # counting all turns
        self.turn_count = 0
        # current player - starts with the one following the dealer
        self.current_player = self.players[list(self.players.keys())[1]]
        print('current_player', self.current_player)
        # first shuffling...
        self.shuffle()
        # ...then dealing
        self.deal()
        # add initial empty trick
        self.add_trick(self.current_player)

    def shuffle(self):
        """
        shuffle cards
        """
        shuffle(self.cards)

    def deal(self):
        """
        deal cards
        """
        for player in self.players.values():
            player.remove_all_cards()
            for card in range(self.cards_per_player):
                # cards are given to players so the can be .pop()ed
                player.add_card(self.cards.pop())

    def add_trick(self, player):
        """
        adds empty trick which will be filled by players one after another
        """
        self.tricks.append(Trick())
        self.current_player = player

    @property
    def current_trick(self):
        """
        enable access to current trick
        """
        return self.tricks[-1]

    @property
    def previous_trick(self):
        """
        return previous trick to enable reclaiming
        """
        return self.tricks[-2]

    def get_next_player(self):
        """
        get player for next turn
        """

        current_player_index = [x.name for x in self.order].index(self.current_player.name)

        if current_player_index < 3:
            # set new current player
            self.current_player = self.order[current_player_index + 1]
        else:
            self.current_player = self.order[0]
        # current player is the next player
        return self.current_player

    def is_finished(self):
        """
        check if round is over - reached when all cards are played
        """
        print(len(Deck.cards), self.turn_count)
        return len(Deck.cards) == self.turn_count

    def get_score(self):
        score = {}
        for trick in self.tricks:
            if trick.owner:
                if trick.owner.name not in score:
                    score[trick.owner.name] = 0
                for card in trick.cards:
                    score[trick.owner.name] += card.value
        return score

    def tell_players_about_opponents(self):
        """
        give players info about whom they are playing against - interesting for HUD display
        """
        for player in self.players.values():
            player_index = [x.name for x in self.order].index(player.name)
            player_order_view = copy(self.order)
            for i in range(player_index):
                player_order_view.append(player_order_view.pop(0))
            player.left = player_order_view[1]
            player.opposite = player_order_view[2]
            player.right = player_order_view[3]



class Table:
    """
    Definition of a table used by group of players
    """

    def __init__(self, name):
        # what table?
        self.name = name
        # default empty
        self.order = []
        self.rounds = []
        self.players_ready = []

    def add_player(self, player):
        """
        adding just one player to the party
        """
        # str as well as Player object is OK
        if type(player) is str:
            player = Player(player)
        self.players[player.name] = player

    def add_round(self):
        """
        only 4 players can play at once - find out who and start a new round
        """
        # since Python 3.6 or 3.7 dicts are ordered
        current_players = {}
        for name in self.order[:4]:
            current_players[name] = self.players[name]
        self.rounds.append(Round(current_players))

    def shift_players(self):
        """
        last dealer is moved to the end of the players list
        """
        self.order.append(self.order.pop(0))

    @property
    def current_round(self):
        return self.rounds[-1]

    def add_ready_player(self, player):
        """
        organize players who are ready for the next round in a list
        """
        self.players_ready.append(player)

    def reset_ready_players(self):
        self.players_ready = []

class Game:
    """
    organizes tables
    """
    def __init__(self):
        # very important for game - some randomness
        seed()
        # store tables
        self.tables = {}

        # get players from CouchDB
        self.players = {}
        for player_id, document in db.player_documents_by_player_id().items():
            self.players[player_id] = Player(document_id=document['_id'])
            self.players[player_id]['bla'] = 'blubb'
            self.players[player_id].save()
            print(self.players[player_id])
            pass


    def add_player(self, player_id, document_id=''):
        """
        adds a new player
        """
        if player_id not in self.players:
            self.players[player_id] = Player(player_id=player_id)
            #self.players[player_id].save()
        else:
            self.players[player_id] = Player(document_id=document_id)
        return self.players[player_id]

    def add_table(self, table_id, document_id=''):
        """
        adds a new table (to sit and play on, no database table!)
        """

        if table_id not in self.tables:
            self.tables[table_id] = Table(table_id=table_id)

        if Table.query.filter_by(name=name).first() is None:
            table = Table(name)
            self.tables[name] = table
            db.session.add(table)
        else:
            self.tables[name] = Table.query.filter_by(name=name).first()

        db.session.commit()

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


# # # initialize database - has to be done here
# db.create_all()
# db.session.commit()

# initialize game, load players etc.
game = Game()

def test_game():
    #game.add_table('test')
    for player_id, document in db.player_documents_by_player_id().items():
        player = game.add_player(player_id, document_id=document['_id'])
        #game.tables['test'].add_player(player)
    #game.tables['test'].order = ['test1', 'test2', 'test3', 'test4', 'test5']
    #game.tables['test'].order = ['test1', 'test2', 'test3', 'test4']

    #game.tables['test'].add_round()


def test_database():
    for test_player in ('admin', 'test1', 'test2', 'test3', 'test4', 'test5', 'test6'):
        if test_player not in db.player_documents_by_player_id():
            player = game.add_player(player_id=test_player)
            player.set_password(test_player)
            db.add(player)

