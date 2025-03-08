# Utilizar una imagen base compatible con Apache y mod_wsgi
FROM python:3.11-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    apache2 \
    libapache2-mod-wsgi-py3 \
    mariadb-client \
    build-essential \
    libssl-dev \
    libffi-dev \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Configurar la zona horaria
ENV TZ=Europe/Madrid
RUN apt-get update && apt-get install -y tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Crear un usuario para ejecutar la aplicación
RUN adduser --disabled-password --gecos '' apiuser

# Copiar el código de la aplicación
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Hacer que el script de entrada sea ejecutable
RUN chmod +x /app/docker-entrypoint.sh

# Exponer el puerto (se especificará en el archivo .env)
EXPOSE ${PORT}

# Establecer el script de entrada
ENTRYPOINT ["/app/docker-entrypoint.sh"]