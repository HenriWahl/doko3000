# database models, e.g. users

from flask_login import UserMixin
from werkzeug.security import check_password_hash,\
                       generate_password_hash

from doko3000 import db,\
                     login


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    password_hash = db.Column(db.String(128))

    def __repr__(self):
        """
        representation
        """
        return f'<User {self.username}>'

    def set_password(self, password):
        """
        create hash of given password
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """
        compare hashed password with given one
        """
        return check_password_hash(self.password_hash, password)

# no database model but an object too
class BroadcastMessage:
    """
    broadcast message for socket.io
    """
    def __init__(self, name, content):
        self.name = name
        self.content = content

@login.user_loader
def load_user(id):
    return User.query.get(int(id))


def test_models():
    for test_user in ('test1', 'test2'):
        if User.query.filter_by(username=test_user).first() is None:
            user = User(username=test_user)
            user.set_password(test_user)
            db.session.add(user)
            db.session.commit()
