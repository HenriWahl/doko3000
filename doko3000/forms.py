# forms

from flask_wtf import FlaskForm
from wtforms.fields import StringField,\
                    PasswordField,\
                    SubmitField
from wtforms.validators import DataRequired

class Login(FlaskForm):
    player_id = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log in')
