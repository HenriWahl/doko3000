# miscellaneous stuff fitting nowhere else

ACCEPTED_JSON_MIMETYPES = ['*/*', 'text/javascript', 'application/json']

MESSAGE_LOGIN_FAILURE = "Login-Fehler"

def is_xhr(request):
    """
    request.is_xhr() got kicked out but is still useful so it reincarnates here
    """
    if request.accept_mimetypes.accept_json and \
            request.accept_mimetypes.best in ACCEPTED_JSON_MIMETYPES:
        return True
    return False


def get_hash(player1_id, player2_id):
    """
    return hash of player IDs for exchange management - sorted to unique
    """
    return ''.join(sorted([player1_id, player2_id]))
