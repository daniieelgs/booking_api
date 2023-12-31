from marshmallow import Schema, fields, validate

from marshmallow import Schema, fields

class PublicLocalSchema(Schema):
    id = fields.Str(required=True, dump_only=True)
    name = fields.Str(required=True)
    tlf = fields.Str(required=True)
    email = fields.Str(required=True)
    description = fields.Str()
    address = fields.Str()
    postal_code = fields.Str()
    village = fields.Str()
    province = fields.Str()
    location = fields.Str(required=True)
    datetime_created = fields.DateTime(required=True, dump_only=True)
    datetime_updated = fields.DateTime(required=True, dump_only=True)

class LocalSchema(PublicLocalSchema):
    password = fields.Str(required=False, load_only=True)
    password_generated = fields.Str(required=False, dump_only=True)
    
class LocalTokensSchema(Schema):
    access_token = fields.Str(required=False, dump_only=True)
    refresh_token = fields.Str(required=False, dump_only=True)
    local = fields.Nested(LocalSchema(), dump_only=True)
    
class LoginLocalSchema(Schema):
    email = fields.Str(required=True)
    password = fields.Str(required=True)
    
    
class ServiceSchema(Schema):
    id = fields.Int(required=True, dump_only=True)
    name = fields.Str(required=True)
    description = fields.Str()
    duration = fields.Int(required=True)
    price = fields.Float(required=True)
    work_group = fields.Int(required=True, load_only=True)
    datetime_created = fields.DateTime(dump_only=True)
    datetime_updated = fields.DateTime(dump_only=True)
class WorkGroupSchema(Schema):
    id = fields.Int(required=True, dump_only=True)
    name = fields.Str(required=True)
    description = fields.Str()
    local_id = fields.Str(required=True, dump_only=True)
    datetime_created = fields.DateTime(dump_only=True)
    datetime_updated = fields.DateTime(dump_only=True)
        
    
class PublicWorkerSchema(Schema):
    id = fields.Int(required=True, dump_only=True)
    name = fields.Str(required=True)
    last_name = fields.Str()
    image = fields.Str()
    
class WorkerSchema(PublicWorkerSchema):
    email = fields.Str()
    tlf = fields.Str()
    datetime_created = fields.DateTime(dump_only=True)
    datetime_updated = fields.DateTime(dump_only=True)
    work_groups = fields.List(fields.Int(), required=True, load_only=True)

class PublicWorkGroupWorkerSchema(WorkGroupSchema):
    workers = fields.Nested(PublicWorkerSchema, many=True, dump_only=True)

class WorkGroupWorkerSchema(WorkGroupSchema):
    workers = fields.Nested(WorkerSchema, many=True, dump_only=True)
    
class WorkGroupServiceSchema(WorkGroupSchema):
    services = fields.Nested(ServiceSchema, many=True, dump_only=True)
class WorkerWorkGroupSchema(WorkerSchema):
    work_groups = fields.Nested(WorkGroupServiceSchema(), many=True, dump_only=True)
class PublicWorkerWorkGroupSchema(PublicWorkerSchema):
    work_groups = fields.Nested(WorkGroupServiceSchema(), many=True, dump_only=True)

class ServiceWorkGroup(ServiceSchema):
    work_group = fields.Nested(PublicWorkGroupWorkerSchema(), dump_only=True)
    
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

class BookingSchema(PublicBookingSchema):
    client_name = fields.Str(required=True)
    client_tlf = fields.Str(required=True)
    comment = fields.Str()
    datetime_created = fields.DateTime(dump_only=True)
    datetime_updated = fields.DateTime(dump_only=True)
    status = fields.Nested(StatusSchema(), dump_only=True)
    total_price = fields.Float(required=True, dump_only=True)
    services = fields.Nested(ServiceSchema(), many=True, dump_only=True)
    
    services_ids = fields.List(fields.Int(), required=True, load_only=True)
    worker_id = fields.Int(required=False, load_only=True)
    
class NewBookingSchema(Schema):
    booking = fields.Nested(BookingSchema(), required=True)
    session_token = fields.Str(required=True)
    timeout = fields.Float(required=True)
    
class BookingAdminSchema(BookingSchema):
    new_status = fields.Str(required=True, load_only=True)
    
class ImageSchema(Schema):
    url = fields.Str(required=True)
    
class BookingParams(Schema):
    date = fields.Date(required=False, description='Specify a date to view reservations for the entire day')
    datetime_init = fields.DateTime(required=False, description='Specify an initial datetime')
    datetime_end = fields.DateTime(required=False, description='Specify an end datetime')
    format = fields.Str(description='Specify the format of date parameters. Default: %Y-%m-%d %H:%M:%S')
    worker_id = fields.Int(required=False, description='Worker ID to filter bookings')
    work_group_id = fields.Int(required=False, description='Work group ID to filter bookings')
    
class BookingWeekParams(BookingParams):
    days = fields.Int(required=False, description='Specify the number of days to view reservations. Default: 7 days')
    
class BookingAdminParams(BookingParams):
    status = fields.Str(required=False, description='Specify the status to filter bookings (ej: C,P).')
    
class BookingAdminWeekParams(BookingWeekParams):
    status = fields.Str(required=False, description='Specify the status to filter bookings (ej: C,P).')
    
class BookingSessionParams(Schema):
    session = fields.Str(required=True)
    
class DeleteParams(Schema):
    force = fields.Bool(required=False, description='Force delete item even if it has bookings.')
    comment = fields.Str(required=False, description='Comment to add to the bookings if force is True.')
    
class UpdateParams(Schema):
    force = fields.Bool(required=False, description='Force update item even if it has bookings.')
