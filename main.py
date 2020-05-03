#!/usr/bin/env python3
#
# ©2020 Henri Wahl
#
# Attempt to play good ol' Doppelkopf online
#

from doko3000 import app,\
                     socketio

from doko3000.game import test_database

#test_game()
test_database()


if __name__ == '__main__':
    socketio.run(app,
                 host='::',
                 debug=True)
