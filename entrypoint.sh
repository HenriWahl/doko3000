#!/bin/bash

# unprivileged gunicorn can't read the key files if it has no rights/ownership
chown doko3000:doko3000 doko3000/data/tls/privkey.pem
chown doko3000:doko3000 doko3000/data/tls/cert.pem

# pem files from letsencrypt can be mounted by docker run
gunicorn --user doko3000\
         --group doko3000\
         --worker-class eventlet\
         --workers 1\
         --keyfile doko3000/data/tls/privkey.pem\
         --certfile doko3000/data/tls/cert.pem\
         --log-level DEBUG\
         --bind :8000\
         main:app

