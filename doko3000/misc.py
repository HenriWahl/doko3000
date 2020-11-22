# miscellaneous stuff fitting nowhere else

from flask_wtf import FlaskForm
from wtforms.fields import StringField,\
                    PasswordField,\
                    SubmitField
from wtforms.validators import DataRequired

ACCEPTED_JSON_MIMETYPES = ['*/*', 'text/javascript', 'application/json']


class Login(FlaskForm):
    player_id = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


# request.is_xhr()-replacement
def is_xhr(request):
    if request.accept_mimetypes.accept_json and \
            request.accept_mimetypes.best in ACCEPTED_JSON_MIMETYPES:
        return True
    return False


def debug(message):
    """
    simple debugging facility
    """
    print(message)