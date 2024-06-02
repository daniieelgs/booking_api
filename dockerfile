FROM python:3.11.9-alpine

WORKDIR /app

RUN apk add --no-cache gcc musl-dev linux-headers mariadb-client

#Set date and time Madrid/Europe
ENV TZ=Europe/Madrid

RUN apk add --no-cache tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN adduser --disabled-password --gecos '' apiuser

RUN mkdir ./private
RUN mkdir ./private/logs

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt
RUN pip install gunicorn

COPY . .

RUN chmod -R 777 /app
RUN chown -R apiuser:apiuser /app

USER apiuser

CMD ["sh", "-c", "if [ \"$FLASK_ENV\" = 'production' ]; then \
                    exec gunicorn --bind $FLASK_RUN_HOST:$FLASK_RUN_PORT --certfile=/etc/ssl/certs/fullchain.pem --keyfile=/etc/ssl/private/privkey.pem --workers $FLASK_RUN_WORKERS --timeout $FLASK_RUN_TIMEOUT --access-logfile '-' --error-logfile '-' app:app; \
                 else \
                    exec flask run --host=$FLASK_RUN_HOST --port=$FLASK_RUN_PORT; \
                 fi"]