# miscellaneous stuff fitting nowhere else

ACCEPTED_JSON_MIMETYPES = ['*/*', 'text/javascript', 'application/json']

# request.is_xhr()-replacement
def is_xhr(request):
    if request.accept_mimetypes.accept_json and \
            request.accept_mimetypes.best in ACCEPTED_JSON_MIMETYPES:
        return True
    return False
