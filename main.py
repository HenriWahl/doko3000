#!/usr/bin/env python3
#
# ©2021 Henri Wahl
#
# Attempt to play good ol' Doppelkopf online
#

from doko3000 import app,\
                     socketio


if __name__ == '__main__':
    socketio.run(app,
                 host='::',
                 debug=True)
