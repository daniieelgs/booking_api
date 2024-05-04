FROM python:3.11.9-alpine

WORKDIR /app

RUN apk add --no-cache gcc musl-dev linux-headers

RUN apk add --no-cache mariadb-client

RUN mkdir ./logs

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt
RUN pip install gunicorn

COPY . .

CMD ["sh", "-c", "if [ \"$FLASK_ENV\" = 'production' ]; then \
                    exec gunicorn --bind $FLASK_RUN_HOST:$FLASK_RUN_PORT --workers $FLASK_RUN_WORKERS --timeout $FLASK_RUN_TIMEOUT --access-logfile '-' --error-logfile '-' app:app; \
                 else \
                    exec flask run --host=$FLASK_RUN_HOST --port=$FLASK_RUN_PORT; \
                 fi"]