FROM python:3.9-alpine
LABEL maintainer=henri.wahl@mailbox.org

RUN apk update &&\
    apk upgrade

COPY . /doko3000
WORKDIR /doko3000

RUN pip install -r requirements.txt

# run gunicorn workers as unprivileged user
RUN adduser -D doko3000

# entrypoint.sh runs gunicorn
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

