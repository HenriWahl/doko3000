#!/usr/bin/env python3
#
# ©2020 Henri Wahl
#
# Attempt to play good ol' Doppelkopf online
#

from game import test_game

from web import app,\
                socketio,\
                Web
web = Web()

test_game()

if __name__ == '__main__':
    socketio.run(app,
                 host='::',
                 debug=True)
