#!/usr/bin/env python3
#
# small command line tool
#

import click

from doko3000.config import DummyApp
from doko3000.database import DB

app = DummyApp()
db = DB(app)

@click.group()
def run():
    pass

@run.command(help='Add player <player> with password <password>')
@click.argument('player_id')
@click.argument('password')
def add_player(player_id):
    click.echo(db.couch.all_dbs())

if __name__ == '__main__':
    run()
