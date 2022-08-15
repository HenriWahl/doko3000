from os import environ
from pathlib import Path
from re import findall

def get_version():
    """
    extract version info from file git_info, fallback to none if not existing
    :return:
    """
    # default
    version = 'n/a'
    try:
        # check if file git_info exists from Dockerfile
        git_info_path = Path('git_info')
        if git_info_path.exists():
            # read it
            git_info_text = git_info_path.read_text()
            git_info_list = git_info_text.split(' ')
            # at least the commit number is taken as version
            if 'commit ' in git_info_text:
                version = git_info_list[1]
            # if there is a tag take it as version
            if 'tag: ' in git_info_text:
                # git log info looks like 'commit 9092ff267e66b30c8ce242df0e45ff558e9ded62 (tag: v2.4.13, menu_at_index)'
                # so it takes some afford to analyze it
                git_info_text_brackets_list = findall(r'\(.*?\)', git_info_text)
                if len(git_info_text_brackets_list) == 1:
                    # get rid of brackets
                    git_info_text_brackets = git_info_text_brackets_list[0].lstrip('(').rstrip(')')
                    for info in git_info_text_brackets.split(','):
                        # finally some tag info
                        if info.strip().startswith('tag: '):
                            version = info.strip().split(' ')[1]
    # version is not too important so it is OK if it is simply catched
    except Exception as error:
        print(error)
    return version

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
    # get version from file
    VERSION = get_version()
