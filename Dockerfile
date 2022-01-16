# only build and install pip stuff here
FROM python:3.9-alpine
LABEL maintainer=henri.wahl@mailbox.org

RUN apk update &&\
    apk upgrade

# needed to build brotli
RUN apk add gcc \
            g++ \
            libc-dev

COPY . /doko3000
WORKDIR /doko3000

RUN pip install --requirement requirements.txt --user

# run gunicorn workers as unprivileged user
RUN adduser -D doko3000

# entrypoint.sh runs gunicorn
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
