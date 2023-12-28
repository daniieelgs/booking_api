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
    
class WorkerWorkGroupSchema(WorkerSchema):
    work_groups = fields.Nested(WorkGroupSchema(), many=True, dump_only=True)
class PublicWorkerWorkGroupSchema(PublicWorkerSchema):
    work_groups = fields.Nested(WorkGroupSchema(), many=True, dump_only=True)
    
class ServiceSchema(Schema):
    id = fields.Int(required=True, dump_only=True)
    name = fields.Str(required=True)
    description = fields.Str()
    duration = fields.Int(required=True)
    price = fields.Float(required=True)
    work_group = fields.Int(required=True, load_only=True)
    datetime_created = fields.DateTime(dump_only=True)
    datetime_updated = fields.DateTime(dump_only=True)
    
class WorkGroupServiceSchema(WorkGroupSchema):
    services = fields.Nested(ServiceSchema, many=True, dump_only=True)

class ServiceWorkGroup(ServiceSchema):
    work_group = fields.Nested(WorkGroupSchema(), dump_only=True)
    
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
    datetime = fields.DateTime(required=True)
    datetime_end = fields.DateTime(required=True, dump_only=True)
    worker = fields.Nested(WorkerSchema(), dump_only=True)    

class BookingSchema(PublicBookingSchema):
    client_name = fields.Str(required=True)
    client_tlf = fields.Str(required=True)
    comment = fields.Str()
    datetime_created = fields.DateTime(dump_only=True)
    datetime_updated = fields.DateTime(dump_only=True)
    status = fields.Nested(StatusSchema(), dump_only=True)
    
    services_ids = fields.List(fields.Int(), required=True, load_only=True)
    worker_id = fields.Int(required=False, load_only=True)
    format = fields.Str(required=False, load_only=True)
    