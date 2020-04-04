FROM python:3.7
LABEL maintainer=h.wahl@ifw-dresden.de

RUN apt -y update &&\
    apt -y upgrade

RUN pip install --upgrade pip

RUN pip install flask \
                flask-socketio \
                https://github.com/HenriWahl/bootstrap-flask/archive/master.zip

