#!/bin/bash

# Ruta del proyecto
dockerFolder="docker"

# Mensaje de inicio
echo "Iniciando el proceso de construcción de imágenes locales..."

chmod +x "$dockerFolder/docker-entrypoint.sh"

# Construir la imagen base
docker build -t booking-base -f "$dockerFolder/Dockerfile.base" .
if [ $? -ne 0 ]; then
    echo "Error construyendo la imagen base."
    exit 1
fi

# Construir la imagen de Flask
docker build -t booking-flask -f "$dockerFolder/Dockerfile.flask" .
if [ $? -ne 0 ]; then
    echo "Error construyendo la imagen de Flask."
    exit 1
fi

# Finalización
echo "Construcción de imágenes completada con éxito."