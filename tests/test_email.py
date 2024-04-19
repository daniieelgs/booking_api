# python -m unittest .\tests\test_booking.py

import datetime
import json
import unittest
from flask_testing import TestCase
from app import create_app, db
from globals import CANCELLED_STATUS, CONFIRMED_STATUS, DONE_STATUS, PENDING_STATUS, WEEK_DAYS, DEBUG
from tests import ConfigTest, getUrl, setParams
from tests.configure_local_base import configure

ENDPOINT = 'booking'

class TestEmail(TestCase):
    def create_app(self):
        self.config_test = ConfigTest(waiter_booking_status=0)
        app = create_app(self.config_test)
        return app

    def setUp(self):

        db.create_all()
        self.config_test.config(db = db)
        self.admin_token = self.config_test.ADMIN_TOKEN

    def tearDown(self):

        db.session.remove()
        db.drop_all()
        self.config_test.drop(self.local.locals)
        
    def configure_local(self):
        self.local = configure(self.client, self.admin_token, self.assertEqual, 0)

    def post_booking_admin(self, booking):
        return self.client.post(getUrl(ENDPOINT, 'admin'), data=json.dumps(booking), headers={'Authorization': f"Bearer {self.admin_token}"}, content_type='application/json')
   
    def post_booking(self, booking):
        return self.client.post(getUrl(ENDPOINT, 'local', self.local.local['id']), data=json.dumps(booking), content_type='application/json')
    
    def post_booking_local(self, booking, **params):
        return self.client.post(setParams(getUrl(ENDPOINT), **params), data=json.dumps(booking), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json')
    
    def cancel_booking(self, session, data = None):
        return self.client.delete(setParams(getUrl(ENDPOINT), session=session), content_type='application/json') if data is None else self.client.delete(setParams(getUrl(ENDPOINT), session=session), data=json.dumps(data), content_type='application/json')
    
    def cancel_booking_admin(self, id, data = None):
        return self.client.delete(setParams(getUrl(ENDPOINT, 'cancel', id)), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json') if data is None else self.client.delete(setParams(getUrl(ENDPOINT, id)), data=json.dumps(data), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json')
  
    def update_booking_admin(self, id, booking):
        return self.client.put(getUrl(ENDPOINT, id), data=json.dumps(booking), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json')
    
    def patch_booking_admin(self, id, booking):
        return self.client.patch(getUrl(ENDPOINT, id), data=json.dumps(booking), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json')
    
    
    def update_booking(self, session, booking):
        return self.client.put(setParams(getUrl(ENDPOINT), session=session), data=json.dumps(booking), content_type='application/json')
    
    def patch_booking(self, session, booking):
        return self.client.patch(setParams(getUrl(ENDPOINT), session=session), data=json.dumps(booking), content_type='application/json')
    
    
    def confirm_booking(self, session):
        return self.client.get(setParams(getUrl(ENDPOINT, 'confirm'), session=session), content_type='application/json')
    
    def confirm_booking_admin(self, id):
        return self.client.get(setParams(getUrl(ENDPOINT, 'confirm', id)), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json')
    
    
    def get_booking_admin(self, id):
        return self.client.get(getUrl(ENDPOINT, id), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json')
    
    def get_booking(self, session):
        return self.client.get(setParams(getUrl(ENDPOINT), session=session), content_type='application/json')
    
    def get_bookings(self, **params):
        return self.client.get(setParams(getUrl(ENDPOINT, 'local', self.local.local['id']), **params), content_type='application/json')
    
    def get_bookings_admin(self, **params):
        return self.client.get(setParams(getUrl(ENDPOINT, 'all'), **params), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json')
    
    def delete_booking_admin(self, id):
        return self.client.delete(getUrl(ENDPOINT, id), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json')
          
    def test_integration_email(self):
        
        self.configure_local()
        
        self.bookings = []
        
        time = (datetime.datetime.strptime(self.local.timetable[0]['opening_time'], "%H:%M:%S")).strftime("%H:%M:%S")
        data = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        booking = {
            "client_name": "Client Test",
            "client_tlf": "123456789",
            "client_email": "client@example.com",
            "datetime_init": f"{data} {time}",
            "services_ids": [self.local.services[0]['id'], self.local.services[1]['id']]
        }
        
        #1. Comprobar envio de emails
        
        #2. Comprobar control de envio de emails
        
            #2.1. Control de envio de emails por dia
            
            #2.2. Control de envio de emails por mes
            
            #2.3. Control de envio de emails por dia y mes
            
            #2.4. Comprobar reseteos
            
            #2.5. Comprobar limite de emails en una configuracion
            
            #2.6. Comprobar limite de emails en todas las configuraciones
            
            #2.7. Comprobar limite de emails en todas las configuraciones y reseteos
        
        #3. Comprobar cancelacion automatica de emails
            #3.1. Sin confirmar reserva
            
            #3.2. Confirmando reserva
            
        #4. Comprobar email de confirmacion
        
        #5. Comprobar email de cancelacion
        
        #6. Comprobar email de actualizacion
        
        #7. Comprobar email de notificacion por parte del local
            #7.1. Creando reserva
            
            #7.2. Actualizando reserva
            
            #7.3. Cancelando reserva
    