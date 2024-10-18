# Ruta del proyecto
$dockerFolder = "docker"

# Imprimir mensaje de inicio
Write-Host "Iniciando el proceso de construcción de imágenes locales..."

# Construir la imagen base
docker build -t booking-base -f "$dockerFolder/Dockerfile.base" .
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error construyendo la imagen base." -ForegroundColor Red
    exit 1
}

# Construir la imagen de Flask
docker build -t booking-flask -f "$dockerFolder/Dockerfile.flask" .
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error construyendo la imagen de Flask." -ForegroundColor Red
    exit 1
}

# Finalización
Write-Host "Construcción de imágenes completada con éxito." -ForegroundColor Green

# Levantar los servicios con Docker Compose
docker-compose -f "$dockerFolder/docker-compose.yml" up
