#!/usr/bin/env python3
#
# ©2020-2022 Henri Wahl
#
# Attempt to play good ol' Doppelkopf online
#

from doko3000 import app,\
                     socketio


if __name__ == '__main__':
    socketio.run(app,
                 host='::')
