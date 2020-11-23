#!/bin/bash

# pem files from letsencrypt can be mounted by docker run
gunicorn --user doko3000\
         --group doko3000\
         --worker-class eventlet\
         --workers 1\
         --log-level DEBUG\
         --bind :5000\
         main:app