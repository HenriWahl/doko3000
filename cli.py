#!/usr/bin/env python3
#
# small command line tool
#

import click

from doko3000.config import DummyApp
from doko3000.database import DB
from doko3000.game import Game

app = DummyApp()
db = DB(app)
game = Game(db)
game.initialize_components()

@click.group()
def run():
    pass

@run.command(help='Add player <player> with password <password>')
@click.argument('player_id')
@click.argument('password')
def add_player(player_id):
    print(game)
if __name__ == '__main__':
    run()
