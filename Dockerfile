FROM python:3.8
LABEL maintainer=henri.wahl@t-online.de

RUN apt -y update &&\
    apt -y upgrade
RUN python -m pip install --upgrade pip

COPY ./ /doko3000
WORKDIR /doko3000

RUN pip install -r requirements.txt

RUN useradd doko3000

ENV FLASK_APP=main.py
CMD ["flask", "run", "--host", "::"]
