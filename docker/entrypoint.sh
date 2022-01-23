#!/bin/ash

# check if running inside PyCharm
if [[ -v PYCHARM_HOSTED ]];
  then
    # when running from PyCharm just pass all arguments to enable debugger
    $@
  else
    # runs as unprivileged user
    gunicorn --user doko3000 \
             --group doko3000 \
             --worker-class eventlet \
             --workers 1 \
             --log-level ERROR \
             --bind :5000 \
             main:app
fi