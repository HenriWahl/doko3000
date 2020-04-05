from copy import deepcopy
from random import seed,\
                   shuffle


class Card:
    """
    one single card
    """

    def __init__(self, symbol, rank):
        """
        symbol, rank and value come from deck
        """
        self.symbol = symbol
        # value is needed for counting score at the end
        self.rank, self.value = rank


class Deck:
    """
    full deck of cards - enough to be static
    """
    SYMBOLS = ('Schell',
               'Herz',
               'Grün',
               'Eichel')
    RANKS = {'Zehn':10,
             'Bube':2,
             'Dame':3,
             'König':4,
             'Ass':11}
    NUMBER = 2 # Doppelkopf :-)!
    cards = []

    for number in range(NUMBER):
        for symbol in SYMBOLS:
            for rank in RANKS.items():
                cards.append(Card(symbol, rank))


class Player:
    """
    one single player in a session
    """
    def __init__(self, name):
        # Name of player
        self.name = name
        # current set of cards
        self.cards = []
        # gained cards
        self.tricks = []

    def get_card(self, card):
        self.cards.append(card)


class Round:
    """
    one round
    """
    def __init__(self, players):
        # if more than 4 players they change for every round
        # changing too because of the position of dealer changes with every round
        self.players = players
        # cards are an important part but makes in a round context only sense if shuffled
        self.cards = []
        # needed to know how many cards are dealed
        # same as number of turns in a round
        self.cards_per_player = len(self.cards) // len(self.players)
        # first shuffling, then dealing
        self.shuffle()
        self.deal()

    def shuffle(self):
        """
        shuffle deck
        """
        self.cards = deepcopy(Deck.cards)
        shuffle(self.cards)

    def deal(self):
        """
        deal cards
        """
        for player in self.players:
            for card in range(self.cards_per_player):
                # cards are given to players so the can be .pop()ed
                player.get_card(self.cards.pop())


class Session:
    """
    Definition of a session
    """
    def __init__(self):
        # ID
        identity = 0
        # who plays?
        self.players = {}
        # how are the players seated?
        self.order = []
        # rounds, one after another
        self.rounds = []
        # latest round
        self.current_round = None

    def add_player(self, player):
        """
        adding just one player to the party
        """
        self.players[player.name] = player

    def add_round(self):
        """
        only 4 players can play at once - find out who and start a new round
        """
        current_players = []
        for name in self.order[:4]:
            current_players.append(self.players[name])
        self.current_round = Round(current_players)


# very important for game
seed()


def test_session():
    session = Session()
    for name in ('Albert', 'Bernd', 'Christoph', 'David', 'Ernie'):
        player = Player(name)
        session.add_player(player)
    session.order = ['Bernd', 'Christoph', 'Albert', 'Ernie', 'David']

    session.add_round()

    print(session.current_round.cards)

    print()