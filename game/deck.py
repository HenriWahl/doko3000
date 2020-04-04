class Card:
    """
    one single card
    """
    # ID
    identity = 0
    # not sure if counting should be included
    value = 0
    # one of 4 colors
    symbol = ''
    # rank
    rank = ''
    # name of file displaying the card
    face = ''

    def __init__(self, symbol, rank):
        self.symbol = symbol
        self.rank = rank

class Deck:
    """
    full deck of cards
    """
    SYMBOLS = ('Schell',
               'Herz',
               'Grün',
               'Eichel')
    RANKS = ('Zehn',
             'Bube',
             'Dame',
             'König',
             'Ass')
    NUMBER = 2 # Doppelkopf :-)!
    cards = []

    def __init__(self):
        for number in self.NUMBER:
            for symbol in self.SYMBOLS:
                for rank in self.RANKS:
                    self.cards.append(symbol, rank)