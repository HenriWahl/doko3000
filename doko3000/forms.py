# forms

from flask_wtf import FlaskForm
from wtforms.fields import StringField,\
                    PasswordField,\
                    SubmitField
from wtforms.validators import DataRequired

class Login(FlaskForm):
    playername = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log in')
