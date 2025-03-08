
# Booking API

## Run
### Create Env Files
- ./docker/.env
- ./db/.env
- ./.env
### Build Docker Images
`docker build -t booking-base -f .\docker\Dockerfile.base .`
`docker build -t booking-flask -f .\docker\Dockerfile.flask .`
### Run Docker Compose
`docker-compose --env-file .\docker\.env -f .\docker\docker-compose.yml up`