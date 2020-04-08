#!/usr/bin/env python3
#
# ©2020 Henri Wahl
#
# Attempt to play good ol' Doppelkopf online
#

from app.game import test_game

from app import app,\
                socketio

test_game()

if __name__ == '__main__':
    socketio.run(app,
                 host='::',
                 debug=True)
