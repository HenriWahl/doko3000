# only build and install pip stuff here
FROM python:3.9-alpine AS build
LABEL maintainer=henri.wahl@mailbox.org

RUN apk update &&\
    apk upgrade

# needed to build brotli
RUN apk add gcc \
            g++ \
            libc-dev

# build and install required pip packages
COPY ./requirements.txt requirements.txt
RUN pip install --requirement requirements.txt

# smaller image for running container
FROM python:3.9-alpine
LABEL maintainer=henri.wahl@mailbox.org

RUN apk update &&\
    apk upgrade

# needed to run brotli
RUN apk add libgcc \
            libstdc++

# due to being installed via pip the installation can be copied without dev files
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build /usr/local/lib /usr/local/lib

COPY . /doko3000
WORKDIR /doko3000

# run gunicorn workers as unprivileged user
RUN adduser -D doko3000

# entrypoint.sh runs gunicorn
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
