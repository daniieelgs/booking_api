from marshmallow import Schema, ValidationError, fields, validate

from marshmallow import Schema, fields
from email_validator import validate_email, EmailNotValidError

class PublicLocalSchema(Schema):
    id = fields.Str(required=True, dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=3, max=45))
    tlf = fields.Str(required=True, validate=validate.Length(min=9, max=13))
    email = fields.Str(required=True, validate=validate.Email())
    description = fields.Str()
    address = fields.Str()
    postal_code = fields.Str()
    village = fields.Str()
    province = fields.Str()
    location = fields.Str(required=True)

class LocalSchema(PublicLocalSchema):
    password = fields.Str(required=False, load_only=True)
    password_generated = fields.Str(required=False, dump_only=True)
    datetime_created = fields.DateTime(required=True, dump_only=True)
    datetime_updated = fields.DateTime(required=True, dump_only=True)
    
class ListSchema(Schema):
    total = fields.Int(required=True, dump_only=True)
    
class LocalListSchema(ListSchema):
    locals = fields.Nested(LocalSchema, many=True, dump_only=True)
    
class LocalTokensSchema(Schema):
    access_token = fields.Str(required=False, dump_only=True)
    refresh_token = fields.Str(required=False, dump_only=True)
    local = fields.Nested(LocalSchema(), dump_only=True)
    
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
    
    services_ids = fields.List(fields.Int(), required=True, load_only=True)
    worker_id = fields.Int(required=False, load_only=True)

class BookingListSchema(ListSchema):
    bookings = fields.Nested(BookingSchema, many=True, dump_only=True)

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
    
class BookingAdminSchema(BookingSchema):
    new_status = fields.Str(required=True, load_only=True)
    
class BookingAdminPatchSchema(BookingPatchSchema):
    new_status = fields.Str(required=False, load_only=True)
    
class ImageSchema(Schema):
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
    
class UpdateParams(Schema):
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
