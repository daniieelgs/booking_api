#!/bin/bash

set -e

# Exportar variables necesarias para envsubst
export PORT SSL_CERT_FILE SSL_KEY_FILE SERVER_NAME

# Generar el archivo de configuración de Apache a partir de la plantilla
envsubst '$PORT,$SSL_CERT_FILE,$SSL_KEY_FILE,$SERVER_NAME' < /app/apache-flask.conf.template > /etc/apache2/sites-available/000-default.conf

# Habilitar módulos necesarios de Apache
a2enmod ssl
a2enmod rewrite
a2enmod wsgi

if [ "$FLASK_ENV" = "production" ]; then
    # Iniciar Apache en primer plano
    exec apachectl -D FOREGROUND
else
    # Ejecutar el servidor de desarrollo de Flask
    exec flask run --host=0.0.0.0 --port=${PORT}
fi