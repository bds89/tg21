# syntax=docker/dockerfile:1

FROM python:3.10
ENV TZ="Europe/Moscow"
WORKDIR /tg21

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

CMD [ "python3", "./tg21.py", "--host=0.0.0.0"]