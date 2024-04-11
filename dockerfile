FROM python:3.11.9-alpine

WORKDIR /app

ENV FLASK_APP app.py

ENV FLASK_RUN_HOST 0.0.0.0

ENV FLASK_RUN_PORT 5000

ENV FLASK_DEBUG 1

RUN apk add --no-cache gcc musl-dev linux-headers

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY . .

CMD flask run --host=$FLASK_RUN_HOST --port=$FLASK_RUN_PORT