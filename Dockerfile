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

RUN pip install --requirement requirements.txt

# BETTER USE MULTI STAGE BUILD HERE

# and not needed anymores
RUN apk del gcc \
            g++ \
            libc-dev

# run gunicorn workers as unprivileged user
RUN adduser -D doko3000

# entrypoint.sh runs gunicorn
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
