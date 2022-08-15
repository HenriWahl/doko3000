# only build and install pip stuff here
FROM python:3.10-alpine AS build
LABEL maintainer=henri.wahl@mailbox.org

RUN apk update &&\
    apk upgrade

# needed to build brotli
RUN apk add gcc \
            g++ \
            git \
            libc-dev

# store git info from doko3000 repo
COPY . /doko3000
WORKDIR /doko3000
RUN git log --max-count 1 --decorate=short | head -n 1 > git_info

# build and install required pip packages
COPY ./requirements.txt requirements.txt
RUN pip install --requirement requirements.txt

# smaller image for running container
FROM python:3.10-alpine
LABEL maintainer=henri.wahl@mailbox.org

RUN apk update &&\
    apk upgrade

# needed to run brotli
RUN apk add libgcc \
            libstdc++

# due to being installed via pip the installation can be copied without dev files
# doko3000 directory has git_info file
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build /usr/local/lib /usr/local/lib
COPY --from=build /doko3000 /doko3000

WORKDIR /doko3000

# run gunicorn workers as unprivileged user
RUN adduser -D doko3000

# entrypoint.sh runs gunicorn
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
