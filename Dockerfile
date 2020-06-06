FROM python:3.8
LABEL maintainer=h.wahl@ifw-dresden.de

RUN apt -y update &&\
    apt -y upgrade

RUN pip install --upgrade pip

RUN pip install click\
                cloudant\
                eventlet\
                flask\
                flask-login\
                flask-socketio\
                flask-wtf\
                gunicorn

COPY ./ /doko3000
WORKDIR /doko3000

# run gunicorn workers as unprivileged user
RUN useradd doko3000

# gunicorn now cares about TLS because secured websockets and flask-socketio did not work
EXPOSE 443

# entrypoint.sh sets the permissions for .pem files to be used by unprivileged gunicorn
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
