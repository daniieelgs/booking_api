
# Endpoint changelog

- **PUT | api/v1/booking/local** : 
    1. Response format
        `
        {
            "local": {
                ...
                "local_settings": {
                    ...
                    "smtp_settings": [{...}, ...]
                }
            },
            "warnings": [...]
        }
        `
        - local_settings es un objeto que contiene la configuración del local, en este caso se agrega un nuevo campo smtp_settings que contiene la configuración de los servidores smtp para el envío de correos electrónicos. También contiene datos como correo de contacto, de soporte, enlace a RRSS, dominio publico, web, enlaces de confirmacion y cancelacion de reservas, etc.
        - Se agrega un campo warnings que contiene advertencias sobre la configuración del local.
        - El campo "booking_timeout" de local_settings define el tiempo en minutos que tiene el usuario para confirmar la reserva. Se usa el valor -1 para desactivar la confirmación de reserva.

- **GET | api/v1/booking/local** : 
    1. Response format
        `
        {
            ...
            "local_settings": {
                "email_contact": "str|null",
                "email_support": "str|null",
                "facebook": "str|null",
                "instagram": "str|null",
                "linkedin": "str|null",
                "maps": "str|null",
                "phone_contact": "str|null",
                "tiktok": "str|null",
                "twitter": "str|null",
                "website": "str|null",
                "whatsapp": "str|null"
                
            }
        }
        `

- **POST | api/v1/booking/local/:local_id**
    1. Request format
        `
        {
            "booking": {...},
            "email_sent": true|false,
            "session_token": "str",
            "timeout": int|null
        }
        `
        - Se agrega el email_sent que indica si se envió el correo de confirmación de la reserva y el timeout que indica el tiempo en minutos que tiene el usuario para confirmar la reserva.

