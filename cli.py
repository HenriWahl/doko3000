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
# done by __init__() already
#game.load_from_db()

@click.group()
def run():
    pass

@run.command(help='Add player <player_id> with password <password>')
@click.argument('player_id')
@click.option('--password', default=None, help='Set password. If not set, the player_id is used.')
@click.option('--is-admin', default=False, is_flag=True, help='Gives admin rights to player.')
def add_player(name, password, is_admin):
    if password == None:
        password = name
    game.add_player(name, password, is_admin)
    # game.players[player_id].set_password(password)
    # if is_admin:
    #     game.players[player_id].is_admin = True

@run.command(help='Add table <table_id>')
@click.argument('table_id', default=False)
def add_table(table_id):
    if table_id:
        game.add_table(table_id)

if __name__ == '__main__':
    run()
