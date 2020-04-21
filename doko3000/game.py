# game logic part of doko3000

from random import seed,\
                   shuffle


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
             #'Unter': 2,
             #'Ober': 3,
             #'König': 4,
             'Ass': 11}
    #NUMBER = 2 # Doppelkopf :-)!
    NUMBER = 1 # Debugging
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


class Player:
    """
    one single player on a table
    """
    def __init__(self, name):
        # Name of player
        self.name = name
        # current set of cards
        self.cards = []
        # gained cards
        self.tricks = []

    def add_card(self, card):
        self.cards.append(card)

    def remove_all_cards(self):
        self.cards = []

    # def get_cards_as_dict(self):
    #     cards_as_dict = {}
    #     for card in self.cards:
    #         print(card.name, card.id)
    #         cards_as_dict[card.id] = card.name
    #     print(len(self.cards))
    #     return cards_as_dict


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

    def add_turn(self, player, card):
        """
        when player plays card it will be added
        """
        self.players.append(player)
        self.cards.append(card)

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
        # order is important - index 0 is the dealer
        self.order = list(players.values())
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

class Table:
    """
    Definition of a table used by group of players
    """
    def __init__(self, name):
        # ID
        self.id = 0
        # what table?
        self.name = name
        # who plays?
        self.players = {}
        # how are the players seated?
        self.order = []
        # rounds, one after another
        self.rounds = []
        # players who are ready to play the next round
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

    def add_table(self, name):
        """
        adds a new table
        """
        self.tables[name] = Table(name)

    def has_tables(self):
        if len(self.tables) == 0:
            return False
        else:
            return True

    def get_tables(self):
        return self.tables.values()

    def get_tables_names(self):
        return list(self.tables.keys())


game = Game()


def test_game():
    game.add_table('test')
    # for name in ('test1', 'test2', 'test3', 'test4', 'test5'):
    for name in ('test1', 'test2', 'test3', 'test4'):
        player = Player(name)
        game.tables['test'].add_player(player)
    # game.tables['test'].order = ['test1', 'test2', 'test3', 'test4', 'test5']
    game.tables['test'].order = ['test1', 'test2', 'test3', 'test4']

    game.tables['test'].add_round()
