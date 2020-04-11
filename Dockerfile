FROM python:3.7
LABEL maintainer=h.wahl@ifw-dresden.de

RUN apt -y update &&\
    apt -y upgrade

RUN pip install --upgrade pip

RUN pip install eventlet\
                flask\
                flask-login\
                flask-sqlalchemy\
                flask-socketio\
                flask-wtf

COPY ./ /doko3000

WORKDIR /doko3000

RUN mkdir data

EXPOSE 5000

CMD python3 main.py