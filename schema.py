from marshmallow import Schema, ValidationError, fields, validate, pre_load, post_dump

from marshmallow import Schema, fields
from email_validator import validate_email, EmailNotValidError

from globals import MIN_TIMEOUT_CONFIRM_BOOKING, TIMEOUT_CONFIRM_BOOKING
from helpers.security import decrypt_str, encrypt_str

class SmtpSettingsSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=3, max=45))
    host = fields.Str(required=True, validate=validate.Length(min=3, max=100))
    port = fields.Int(required=True, validate=validate.Range(min=0, max=65535))
    user = fields.Str(required=True, validate=validate.Length(min=3, max=100))
    mail = fields.Str(required=True, validate=validate.Email())
    password = fields.Str(required=True)
    priority = fields.Int(required=True, validate=validate.Range(min=0))
    send_per_day = fields.Int(required=False, load_default=0, validate=validate.Range(min=0))
    send_per_month = fields.Int(required=False, load_default=0, validate=validate.Range(min=0))
    max_send_per_day = fields.Int(required=False)
    max_send_per_month = fields.Int(required=False)
    reset_send_per_day = fields.DateTime(required=False)
    reset_send_per_month = fields.DateTime(required=False)
    
    @pre_load
    def encrypt_password_load(self, in_data, **kwargs):
        if 'password' in in_data:
            in_data['password'] = encrypt_str(in_data['password'])
        return in_data

    @post_dump
    def decrypt_password_dump(self, data, **kwargs):
        if 'password' in data:
            data['password'] = decrypt_str(data['password'])
        return data
    
class SmtpSettingsPatchSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=3, max=45))
    new_name = fields.Str(required=False, validate=validate.Length(min=3, max=45))
    remove = fields.Bool(required=False)
    host = fields.Str(required=False, validate=validate.Length(min=3, max=100))
    port = fields.Int(required=False, validate=validate.Range(min=0, max=65535))
    user = fields.Str(required=False, validate=validate.Length(min=3, max=100))
    mail = fields.Str(required=False, validate=validate.Email())
    password = fields.Str(required=False)
    priority = fields.Int(required=False, validate=validate.Range(min=0))
    send_per_day = fields.Int(required=False, validate=validate.Range(min=0))
    send_per_month = fields.Int(required=False, validate=validate.Range(min=0))
    max_send_per_day = fields.Int(required=False, allow_none=True)
    max_send_per_month = fields.Int(required=False, allow_none=True)
    reset_send_per_day = fields.DateTime(required=False, allow_none=True)
    reset_send_per_month = fields.DateTime(required=False, allow_none=True)
    
    @pre_load
    def encrypt_password_load(self, in_data, **kwargs):
        if 'password' in in_data:
            in_data['password'] = encrypt_str(in_data['password'])
        return in_data

    @post_dump
    def decrypt_password_dump(self, data, **kwargs):
        if 'password' in data:
            data['password'] = decrypt_str(data['password'])
        return data

    
class PublicSettingsSchema(Schema):
    website = fields.Str(required=False, validate=validate.URL())
    instagram = fields.Str(required=False, validate=validate.URL())
    facebook = fields.Str(required=False, validate=validate.URL())
    twitter = fields.Str(required=False, validate=validate.URL())
    whatsapp = fields.Str(required=False, validate=validate.URL())
    linkedin = fields.Str(required=False, validate=validate.URL())
    tiktok = fields.Str(required=False, validate=validate.URL())
    maps = fields.Str(required=False, validate=validate.URL())
    email_contact = fields.Str(required=False, validate=validate.Email())
    phone_contact = fields.Str(required=False, validate=validate.Length(min=9, max=13))
    email_support = fields.Str(required=False, validate=validate.Email())
class _LocalSettingsSchema(PublicSettingsSchema):
    domain = fields.Str(required=False, validate=validate.Length(min=0, max=100))
    confirmation_link = fields.Str(required=False, validate=validate.URL())
    cancel_link = fields.Str(required=False, validate=validate.URL())
    update_link = fields.Str(required=False, validate=validate.URL())
    booking_timeout = fields.Int(required=False, load_default=TIMEOUT_CONFIRM_BOOKING, validate=validate.Range(min=-1), allow_none=True)
class LocalSettingsSchema(_LocalSettingsSchema):
    smtp_settings = fields.Nested(SmtpSettingsSchema, many=True, required=False)

class LocalSettingsPatchSchema(_LocalSettingsSchema):
    booking_timeout = fields.Int(required=False, validate=validate.Range(min=-1), allow_none=True)
    smtp_settings = fields.Nested(SmtpSettingsPatchSchema, many=True, required=False)

class PublicLocalSchema(Schema):
    id = fields.Str(required=True, dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=3, max=45))
    description = fields.Str()
    address = fields.Str()
    postal_code = fields.Str()
    village = fields.Str()
    province = fields.Str()
    local_settings = fields.Nested(PublicSettingsSchema, required=False)
    location = fields.Str(required=True)

class LocalSchema(PublicLocalSchema):
    tlf = fields.Str(required=True, validate=validate.Length(min=9, max=13))
    email = fields.Str(required=True, validate=validate.Email())
    password = fields.Str(required=False, load_only=True)
    password_generated = fields.Str(required=False, dump_only=True)
    local_settings = fields.Nested(LocalSettingsSchema, required=False)
    uuid_log = fields.Str(required=False, dump_only=True)
    datetime_created = fields.DateTime(required=True, dump_only=True)
    datetime_updated = fields.DateTime(required=True, dump_only=True)
    
class LocalPatchSchema(Schema):
    name = fields.Str(required=False, validate=validate.Length(min=3, max=45))
    tlf = fields.Str(required=False, validate=validate.Length(min=9, max=13))
    email = fields.Str(required=False, validate=validate.Email())
    description = fields.Str()
    address = fields.Str()
    postal_code = fields.Str()
    village = fields.Str()
    province = fields.Str()
    location = fields.Str(required=False)
    password = fields.Str(required=False, load_only=True)
    local_settings = fields.Nested(LocalSettingsPatchSchema, required=False)
    datetime_created = fields.DateTime(required=False, dump_only=True)
    datetime_updated = fields.DateTime(required=False, dump_only=True)
  
class LocalWarningSchema(Schema):
    local = fields.Nested(LocalSchema, required=False, dump_only=True)
    warnings = fields.List(fields.Str(), required=False, dump_only=True)
    
class ListSchema(Schema):
    total = fields.Int(required=True, dump_only=True)
    
class LocalListSchema(ListSchema):
    locals = fields.Nested(LocalSchema, many=True, dump_only=True)
    
class LocalTokensSchema(Schema):
    access_token = fields.Str(required=False, dump_only=True)
    refresh_token = fields.Str(required=False, dump_only=True)
    local = fields.Nested(LocalSchema(), dump_only=True)
    warnings = fields.List(fields.Str(), required=False, dump_only=True)
    
class LoginLocalSchema(Schema):
    email = fields.Str(required=True)
    password = fields.Str(required=True)
    
class ServiceSchema(Schema):
    id = fields.Int(required=True, dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=3, max=45))
    description = fields.Str()
    duration = fields.Int(required=True, validate=validate.Range(min=0))
    price = fields.Float(required=True, validate=validate.Range(min=0))
    work_group = fields.Int(required=True, load_only=True)
    datetime_created = fields.DateTime(dump_only=True)
    datetime_updated = fields.DateTime(dump_only=True)
class WorkGroupSchema(Schema):
    id = fields.Int(required=True, dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=3, max=45))
    description = fields.Str()
    local_id = fields.Str(required=True, dump_only=True)
    datetime_created = fields.DateTime(dump_only=True)
    datetime_updated = fields.DateTime(dump_only=True)
   
class WorkGroupListSchema(ListSchema):
    work_groups = fields.Nested(WorkGroupSchema, many=True, dump_only=True)
    
class PublicWorkerSchema(Schema):
    id = fields.Int(required=True, dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=3, max=45))
    last_name = fields.Str()
    image = fields.Str()

class PublicWorkerListSchema(ListSchema):
    workers = fields.Nested(PublicWorkerSchema, many=True, dump_only=True)   
class WorkerSchema(PublicWorkerSchema):
    email = fields.Str(validate=validate.Email())
    tlf = fields.Str(validate=validate.Length(min=9, max=13))
    datetime_created = fields.DateTime(dump_only=True)
    datetime_updated = fields.DateTime(dump_only=True)
    work_groups = fields.List(fields.Int(), required=True, load_only=True)

class WorkerListSchema(ListSchema):
    workers = fields.Nested(WorkerSchema, many=True, dump_only=True)

class PublicWorkGroupWorkerSchema(WorkGroupSchema):
    workers = fields.Nested(PublicWorkerSchema, many=True, dump_only=True)

class PublicWorkGroupWorkerListSchema(ListSchema):
    work_groups = fields.Nested(PublicWorkGroupWorkerSchema, many=True, dump_only=True)

class WorkGroupWorkerSchema(WorkGroupSchema):
    workers = fields.Nested(WorkerSchema, many=True, dump_only=True)
    
class WorkGroupWorkerListSchema(ListSchema):
    work_groups = fields.Nested(WorkGroupWorkerSchema, many=True, dump_only=True)

class WorkGroupServiceSchema(WorkGroupSchema):
    services = fields.Nested(ServiceSchema, many=True, dump_only=True)
    
class WorkGroupServiceListSchema(ListSchema):
    work_groups = fields.Nested(WorkGroupServiceSchema, many=True, dump_only=True)
    
class WorkerWorkGroupSchema(WorkerSchema):
    work_groups = fields.Nested(WorkGroupServiceSchema(), many=True, dump_only=True)
class PublicWorkerWorkGroupSchema(PublicWorkerSchema):
    work_groups = fields.Nested(WorkGroupServiceSchema(), many=True, dump_only=True)
class PublicWorkerWorkListGroupSchema(ListSchema):
    workers = fields.Nested(PublicWorkerWorkGroupSchema(), many=True, dump_only=True)
    
class ServiceWorkGroup(ServiceSchema):
    work_group = fields.Nested(PublicWorkGroupWorkerSchema(), dump_only=True)
 
class ServiceWorkGroupListSchema(ListSchema):
    services = fields.Nested(ServiceWorkGroup, many=True, dump_only=True)
    
class WeekDaySchema(Schema):
    weekday = fields.Str(required=True, dump_only=True)
    name = fields.Str(required=True, dump_only=True)
    
class TimetableSchema(Schema):
    id = fields.Int(required=True, dump_only=True)
    opening_time = fields.Time(required=True)
    closing_time = fields.Time(required=True)
    description = fields.Str()
    local_id = fields.Str(required=True, dump_only=True)
    weekday_short = fields.Str(required=True, load_only=True)
    weekday = fields.Nested(WeekDaySchema(), dump_only=True)

class StatusSchema(Schema):
    status = fields.Str(required=True, dump_only=True)
    name = fields.Str(dump_only=True)
    
class PublicBookingSchema(Schema):
    id = fields.Int(required=True, dump_only=True)
    datetime_init = fields.DateTime(required=True)
    datetime_end = fields.DateTime(required=True, dump_only=True)
    worker = fields.Nested(PublicWorkerSchema(), dump_only=True)    
    
class PublicBookingListSchema(ListSchema):
    bookings = fields.Nested(PublicBookingSchema, many=True, dump_only=True)
    
class PublicBookingPatchSchema(Schema):
    id = fields.Int(required=True, dump_only=True)
    datetime_init = fields.DateTime(required=False)
    datetime_end = fields.DateTime(required=True, dump_only=True)
    worker = fields.Nested(PublicWorkerSchema(), dump_only=True)    

class BookingSchema(PublicBookingSchema):
    client_name = fields.Str(required=True, validate=validate.Length(min=3, max=45))
    client_email = fields.Str(required=True, validate=validate.Email())
    client_tlf = fields.Str(required=True, validate=validate.Length(min=9, max=13))
    comment = fields.Str()
    datetime_created = fields.DateTime(dump_only=True)
    datetime_updated = fields.DateTime(dump_only=True)
    status = fields.Nested(StatusSchema(), dump_only=True)
    total_price = fields.Float(required=True, dump_only=True)
    services = fields.Nested(ServiceSchema(), many=True, dump_only=True)
    uuid_log = fields.Str(required=False, dump_only=True)
    services_ids = fields.List(fields.Int(), required=True, load_only=True)
    worker_id = fields.Int(required=False, load_only=True)
        

class BookingPatchSchema(PublicBookingPatchSchema):
    client_name = fields.Str(required=False, validate=validate.Length(min=3, max=45))
    client_email = fields.Str(required=False, validate=validate.Email())
    client_tlf = fields.Str(required=False, validate=validate.Length(min=9, max=13))
    comment = fields.Str()
    datetime_created = fields.DateTime(dump_only=True)
    datetime_updated = fields.DateTime(dump_only=True)
    status = fields.Nested(StatusSchema(), dump_only=True)
    total_price = fields.Float(required=False, dump_only=True)
    services = fields.Nested(ServiceSchema(), many=True, dump_only=True)
    
    services_ids = fields.List(fields.Int(), required=False, load_only=True)
    worker_id = fields.Int(required=False, load_only=True)
    
class NewBookingSchema(Schema):
    booking = fields.Nested(BookingSchema(), required=True)
    session_token = fields.Str(required=True)
    timeout = fields.Float(required=True)
    email_confirm = fields.Bool(required=True, dump_only=True)
    
class BookingAdminSchema(BookingSchema):
    new_status = fields.Str(required=True, load_only=True)
    email_confirm = fields.Bool(required=True, dump_only=True)
    email_confirmed = fields.Bool(required=True, dump_only=True)
    email_cancelled = fields.Bool(required=True, dump_only=True)
    email_updated = fields.Bool(required=True, dump_only=True)    
class BookingAdminPatchSchema(BookingPatchSchema):
    new_status = fields.Str(required=False, load_only=True)
   
class BookingListSchema(ListSchema):
    bookings = fields.Nested(BookingSchema, many=True, dump_only=True)

class BookingAdminListSchema(ListSchema):
    bookings = fields.Nested(BookingAdminSchema, many=True, dump_only=True)
    
class FileSchema(Schema):
    url = fields.Str(required=True)
    
class CommentSchema(Schema):
    comment = fields.Str(required=False)    
    
class BookingParams(Schema):
    date = fields.Date(required=False, description='Espefica una fecha para ver las reservas de todo el día.')
    datetime_init = fields.DateTime(required=False, description='Espefica una fecha y hora inicial para ver las reservas.')
    datetime_end = fields.DateTime(required=False, description='Espefica una fecha y hora final para ver las reservas.')
    format = fields.Str(required=False, description='Espefica el formato de la fecha y hora. Default: %Y-%m-%d %H:%M:%S')
    worker_id = fields.Int(required=False, description='ID del trabajador para filtrar las reservas.')
    work_group_id = fields.Int(required=False, description='ID del grupo de trabajo para filtrar las reservas.')
    free = fields.Bool(required=False, description='Muestra las reservas libres.')
    
class BookingWeekParams(BookingParams):
    days = fields.Int(required=False, description='Espefica el número de días de la semana a visualizar. Default: 7.')
    
class BookingAdminParams(BookingParams):
    status = fields.Str(required=False, description='Especifica el estado para filtrar las reservas (Ej: C,P).')
    name = fields.Str(required=False, description='Espefica el nombre del cliente para filtrar las reservas.')
    email = fields.Str(required=False, description='Espefica el email del cliente para filtrar las reservas.')
    tlf = fields.Str(required=False, description='Espefica el teléfono del cliente para filtrar las reservas.')
    
class BookingAdminWeekParams(BookingWeekParams):
    status = fields.Str(required=False, description='Espefica el estado para filtrar las reservas (Ej: C,P).')
    name = fields.Str(required=False, description='Espefica el nombre del cliente para filtrar las reservas.')
    email = fields.Str(required=False, description='Espefica el email del cliente para filtrar las reservas.')
    tlf = fields.Str(required=False, description='Espefica el teléfono del cliente para filtrar las reservas.')
    
class BookingSessionParams(Schema):
    session = fields.Str(required=True)
    
class DeleteParams(Schema):
    force = fields.Bool(required=False, description='Fuerza la eliminación del item incluso si tiene reservas.')
    comment = fields.Str(required=False, description='Comentario para la eliminación.')
    
class NotifyParams(Schema):
    notify = fields.Bool(required=False, description='Notifica a los clientes de la acción.')
class UpdateParams(NotifyParams):
    force = fields.Bool(required=False, description='Fuerza la actualización del item incluso si tiene reservas.')
    
class LocalAdminParams(Schema):
    name = fields.Str(required=False, description='Espefica el nombre para filtrar locales.')
    email = fields.Str(required=False, description='Espefica el email para filtrar locales.')
    tlf = fields.Str(required=False, description='Espefica el teléfono para filtrar locales.')
    address = fields.Str(required=False, description='Espefica la dirección para filtrar locales.')
    postal_code = fields.Str(required=False, description='Espefica el código postal para filtrar locales.')
    village = fields.Str(required=False, description='Espfica la población para filtrar locales.')
    province = fields.Str(required=False, description='Espfica la provincia para filtrar locales.')
    location = fields.Str(required=False, description='Espfica la zona horaria para filtrar locales.')
    date_created = fields.DateTime(required=False, description='Espfica la fecha de creación para filtrar locales.')
    datetime_init = fields.DateTime(required=False, description='Espfica una fecha y hora inicial de creación para filtrar locales.')
    datetime_end = fields.DateTime(required=False, description='Espfica una fecha y hora final de creación para filtrar locales.')
    
class CloseDaysSchema(Schema):
    id = fields.Int(required=True, dump_only=True)
    datetime_init = fields.DateTime(required=True, description='Fecha de inicio del cierre.')
    datetime_end = fields.DateTime(required=True, description='Fecha de fin del cierre.')
    description = fields.Str(description='Descripción del cierre.')
    
class CloseDaysParams(Schema):
    datetime_init = fields.DateTime(required=False, description='Espefica una fecha y hora inicial para ver los cierres.')
    datetime_end = fields.DateTime(required=False, description='Espefica una fecha y hora final para ver los cierres.')
