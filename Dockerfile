FROM python:3.9
LABEL maintainer=henri.wahl@t-online.de

RUN apt -y update &&\
    apt -y upgrade

COPY . /doko3000
WORKDIR /doko3000

RUN pip install -r requirements.txt

# run gunicorn workers as unprivileged user
RUN useradd doko3000

# entrypoint.sh runs gunicorn
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
