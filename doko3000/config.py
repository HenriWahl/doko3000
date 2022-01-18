from os import environ


class Config:
    TITLE = 'doko3000'
    # to be given by environment variable
    SECRET_KEY = environ.get('SECRET_KEY') or 'dummykey'
    # database
    # CouchDB, according to https://hub.docker.com/_/couchdb
    COUCHDB_URL = environ.get('COUCHDB_URL') or 'http://couchdb:5984'
    COUCHDB_DATABASE = environ.get('COUCHDB_DATABASE') or 'doko3000'
    COUCHDB_USER = environ.get('COUCHDB_USER') or 'admin'
    COUCHDB_PASSWORD = environ.get('COUCHDB_PASSWORD') or 'doko3000'
    # needed for CORS in flask-socketio
    host = environ.get('HOST')
    if host:
        CORS_ALLOWED_ORIGINS = [f'http://{host}', f'https://{host}']
    else:
        CORS_ALLOWED_ORIGINS = []
    # boolize DEBUG environment variable
    if environ.get('DEBUG') and \
            environ['DEBUG'].lower() in ['1', 'true', 'yes']:
        DEBUG = True
        ENV = 'development'
    else:
        DEBUG = False
        ENV = 'production'
    # avoid browser warnings about samesite missing
    SESSION_COOKIE_SAMESITE = 'Strict'
    SESSION_COOKIE_SECURE = True
    # supported MIME types for compression
    COMPRESS_MIMETYPES = [
        'text/html',
        'text/css',
        'text/xml',
        'application/json',
        'application/javascript',
        'application/fvnd.ms-fontobject',
        'application/font-woff',
        'application/font-woff2',
        'image/png',
        'image/svg',
        'image/svg+xml'
    ]
    SEND_FILE_MAX_AGE_DEFAULT = 86400