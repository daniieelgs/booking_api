# python -m unittest .\tests\test_booking.py

import datetime
import json
import unittest
from flask_testing import TestCase
from app import create_app, db
from globals import CANCELLED_STATUS, CONFIRMED_STATUS, DONE_STATUS, PENDING_STATUS, WEEK_DAYS, DEBUG
from tests import ConfigTest, getUrl, setParams
from tests.configure_local_base import configure
from dateutil.relativedelta import relativedelta

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
          
    def get_local_settings(self):
        response = self.client.get(getUrl('local'), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json')
        response = response.json
        return response['local_settings']
          
    def check_email(self):
        post_booking = self.post_booking(self.booking)
                
        self.assertEqual(post_booking.status_code, 201)
        
        response = post_booking.json
        
        self.assertEqual(response['booking']['status']['status'], PENDING_STATUS)
        self.assertEqual(response['email_sent'], True)
    
    def check_control_email(self):
        #2.1. Control de envio de emails por dia y mes
        
        send_day_pre = self.get_local_settings()['smtp_settings'][0]['send_per_day']
        send_month_pre = self.get_local_settings()['smtp_settings'][0]['send_per_month']
        
        post_booking = self.post_booking(self.booking)
        
        self.assertEqual(post_booking.status_code, 201)
        
        response = post_booking.json
        
        self.assertEqual(response['email_sent'], True)
        
        send_day_post = self.get_local_settings()['smtp_settings'][0]['send_per_day']
        send_month_post = self.get_local_settings()['smtp_settings'][0]['send_per_month']
        
        self.assertEqual(send_day_post, send_day_pre + 1)
        self.assertEqual(send_month_post, send_month_pre + 1)        
        
        #2.2. Comprobar reseteos

        send_day_pre = 300
        send_month_pre = 300
        
        self.local.local_settings['smtp_settings'][0]['reset_send_per_day'] = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
        self.local.local_settings['smtp_settings'][0]['send_per_day'] = send_day_pre
        self.local.local_settings['smtp_settings'][0]['reset_send_per_month'] = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
        self.local.local_settings['smtp_settings'][0]['send_per_month'] = send_month_pre
        
        data = self.local.local
        local_id = data.pop('id')
        
        r = self.client.put(getUrl('local'), data=json.dumps(self.local.local),  headers={'Authorization': f"Bearer {self.local.access_token}"}, content_type='application/json')
        
        data['id'] = local_id
        
        print("response:", r.json)
        
        self.assertEqual(r.status_code, 200)
        
        post_booking = self.post_booking(self.booking)
        
        self.assertEqual(post_booking.status_code, 201)
        
        settings = self.get_local_settings()
        
        send_day_post = settings['smtp_settings'][0]['send_per_day']
        send_month_post = settings['smtp_settings'][0]['send_per_month']
        reset_day = settings['smtp_settings'][0]['reset_send_per_day']
        
        self.assertEqual(send_day_post, 1)
        self.assertEqual(send_month_post, send_month_pre + 1)
        
        self.assertEqual(reset_day, (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00"))
                
        response = post_booking.json
                
        self.cancel_booking(response['session_token'])
        
        post_booking = self.post_booking(self.booking)
        
        self.assertEqual(post_booking.status_code, 201)
        
        send_day_post = self.get_local_settings()['smtp_settings'][0]['send_per_day']
        send_month_post = self.get_local_settings()['smtp_settings'][0]['send_per_month']
        
        self.assertEqual(send_day_post, 2)
        self.assertEqual(send_month_post, send_month_pre + 2)
        
        response = post_booking.json
        
        self.cancel_booking(response['session_token'])
        
        self.local.local_settings['smtp_settings'][0]['reset_send_per_month'] = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
        self.local.local_settings['smtp_settings'][0]['reset_send_per_day'] = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")

        self.local.local_settings['smtp_settings'][0]['send_per_day'] = 2
        self.local.local_settings['smtp_settings'][0]['send_per_month'] = 50
        
        data = self.local.local
        local_id = data.pop('id')
        
        r = self.client.put(getUrl('local'), data=json.dumps(self.local.local),  headers={'Authorization': f"Bearer {self.local.access_token}"}, content_type='application/json')
        
        data['id'] = local_id
        
        self.assertEqual(r.status_code, 200)
        
        post_booking = self.post_booking(self.booking)
        
        self.assertEqual(post_booking.status_code, 201)
        
        response = post_booking.json
        
        send_day_post = self.get_local_settings()['smtp_settings'][0]['send_per_day']
        send_month_post = self.get_local_settings()['smtp_settings'][0]['send_per_month']
        reset_month = self.get_local_settings()['smtp_settings'][0]['reset_send_per_month']
        
        self.assertEqual(send_day_post, 3)
        self.assertEqual(send_month_post, 1)
        
        self.assertEqual(reset_month, (datetime.datetime.now() - datetime.timedelta(days=1) + relativedelta(months=+1)).strftime("%Y-%m-%dT00:00:00"))
        
        self.cancel_booking(response['session_token'])
        
        #2.3. Comprobar limite de emails en una configuracion (dia/mes)
                
            #Limite por dia
                
        self.local.local_settings['smtp_settings'][0]['send_per_day'] = self.local.local_settings['smtp_settings'][0]['max_send_per_day']
        
        data = self.local.local
        
        local_id = data.pop('id')
        
        r = self.client.put(getUrl('local'), data=json.dumps(self.local.local),  headers={'Authorization': f"Bearer {self.local.access_token}"}, content_type='application/json')
        
        self.assertEqual(r.status_code, 200)
        
        data['id'] = local_id
        
        send_day_pre0 = self.get_local_settings()['smtp_settings'][0]['send_per_day']
        send_day_pre1 = self.get_local_settings()['smtp_settings'][1]['send_per_day']
        send_month_pre0 = self.get_local_settings()['smtp_settings'][0]['send_per_month']
        
        post_booking = self.post_booking(self.booking)
                
        self.assertEqual(post_booking.status_code, 201)
        
        response = post_booking.json
        
        self.assertEqual(response['email_sent'], True)
          
        settings = self.get_local_settings()
                
        self.assertEqual(settings['smtp_settings'][0]['send_per_day'], send_day_pre0)
        self.assertEqual(settings['smtp_settings'][0]['send_per_month'], send_month_pre0)                

        self.assertEqual(settings['smtp_settings'][1]['send_per_day'], send_day_pre1 + 1)
        
        self.cancel_booking(response['session_token'])
        
            #Limite por mes
        
        self.local.local_settings['smtp_settings'][0]['send_per_month'] = self.local.local_settings['smtp_settings'][0]['max_send_per_month']
        self.local.local_settings['smtp_settings'][0]['send_per_day'] = 0
        self.local.local_settings['smtp_settings'][0]['reset_send_per_day'] = self.local.local_settings['smtp_settings'][0]['reset_send_per_month'] = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
        
        data = self.local.local
        
        local_id = data.pop('id')
        
        r = self.client.put(getUrl('local'), data=json.dumps(data),  headers={'Authorization': f"Bearer {self.local.access_token}"}, content_type='application/json')
        
        self.assertEqual(r.status_code, 200)
        
        data['id'] = local_id
        
        settings = self.get_local_settings()
        
        send_month_pre0 = settings['smtp_settings'][0]['send_per_month']
        send_day_pre0 = settings['smtp_settings'][0]['send_per_day']
        send_day_pre1 = settings['smtp_settings'][1]['send_per_day']
        
        post_booking = self.post_booking(self.booking)
        
        self.assertEqual(post_booking.status_code, 201)
        
        response = post_booking.json
        
        self.assertEqual(response['email_sent'], True)
        
        settings = self.get_local_settings()
        
        self.assertEqual(settings['smtp_settings'][0]['send_per_month'], send_month_pre0)
        self.assertEqual(settings['smtp_settings'][0]['send_per_day'], send_day_pre0)
        self.assertEqual(settings['smtp_settings'][1]['send_per_day'], send_day_pre1 + 1)
        
        self.cancel_booking(response['session_token'])
        
        #2.4. Comprobar limite de emails en todas las configuraciones
        
        self.local.local_settings['smtp_settings'][0]['send_per_day'] = self.local.local_settings['smtp_settings'][0]['max_send_per_day']
        self.local.local_settings['smtp_settings'][1]['send_per_day'] = self.local.local_settings['smtp_settings'][1]['max_send_per_day']

        data = self.local.local
        
        local_id = data.pop('id')
        
        r = self.client.put(getUrl('local'), data=json.dumps(data),  headers={'Authorization': f"Bearer {self.local.access_token}"}, content_type='application/json')
        
        self.assertEqual(r.status_code, 200)
        
        data['id'] = local_id
        
        settings = self.get_local_settings()
        
        send_day_pre0 = settings['smtp_settings'][0]['send_per_day']
        send_day_pre1 = settings['smtp_settings'][1]['send_per_day']
        
        post_booking = self.post_booking(self.booking)
        
        self.assertEqual(post_booking.status_code, 201)
        
        response = post_booking.json
        
        self.assertEqual(response['email_sent'], False)
        
        settings = self.get_local_settings()
        
        self.assertEqual(settings['smtp_settings'][0]['send_per_day'], send_day_pre0)
        self.assertEqual(settings['smtp_settings'][1]['send_per_day'], send_day_pre1)
        
        self.cancel_booking(response['session_token'])
        
        #2.5. Comprobar limite de emails en todas las configuraciones y reseteos
    
            #Resetear por dia
    
        self.local.local_settings['smtp_settings'][0]['reset_send_per_day'] = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
        
        data = self.local.local
        
        local_id = data.pop('id')
        
        r = self.client.put(getUrl('local'), data=json.dumps(data), headers={'Authorization': f"Bearer {self.local.access_token}"}, content_type='application/json')
        
        self.assertEqual(r.status_code, 200)
        
        data['id'] = local_id
        
        settings = self.get_local_settings()
        
        post_booking = self.post_booking(self.booking)
        
        self.assertEqual(post_booking.status_code, 201)
        
        response = post_booking.json
        
        self.assertEqual(response['email_sent'], False)
        
        settings = self.get_local_settings()
        
        self.cancel_booking(response['session_token'])
        
            #Resetear por mes
            
        self.local.local_settings['smtp_settings'][0]['reset_send_per_month'] = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
        
        data = self.local.local
        
        local_id = data.pop('id')
        
        r = self.client.put(getUrl('local'), data=json.dumps(data), headers={'Authorization': f"Bearer {self.local.access_token}"}, content_type='application/json')
        
        self.assertEqual(r.status_code, 200)
        
        data['id'] = local_id
        
        settings = self.get_local_settings()
        
        post_booking = self.post_booking(self.booking)
        
        self.assertEqual(post_booking.status_code, 201)
        
        response = post_booking.json
        
        self.assertEqual(response['email_sent'], True)
        
        settings = self.get_local_settings()
        
        self.assertEqual(settings['smtp_settings'][0]['send_per_day'], 1)
        self.assertEqual(settings['smtp_settings'][0]['send_per_month'], 1)
        
        self.cancel_booking(response['session_token'])

    def check_cancel_confirm_email(self):
        #3.1. Sin confirmar reserva
        
        #3.2. Confirmando reserva
        
        #3.3 Confirmacion automatica de reserva
        pass
    
    def check_email_confirmation(self):
        pass
    
    def check_email_cancellation(self):
        pass
    
    def check_email_update(self):
        pass
    
    def check_email_notification(self):
        #7.1. Creando reserva
        
        #7.2. Actualizando reserva
        
        #7.3. Cancelando reserva
        pass
          
    def test_integration_email(self):
        
        self.configure_local()
        
        self.bookings = []
        
        time = (datetime.datetime.strptime(self.local.timetable[0]['opening_time'], "%H:%M:%S")).strftime("%H:%M:%S")
        data = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        self.booking = {
            "client_name": "Client Test",
            "client_tlf": "123456789",
            "client_email": "client@example.com",
            "datetime_init": f"{data} {time}",
            "services_ids": [self.local.services[0]['id'], self.local.services[1]['id']]
        }
        
        #1. Comprobar envio de emails
        self.check_email()
        
        #2. Comprobar control de envio de emails
        self.check_control_email()
        
        #3. Comprobar cancelacion/confirmacion automatica de emails
        self.check_cancel_confirm_email()
            
        #4. Comprobar email de confirmacion
        self.check_email_confirmation()
        
        #5. Comprobar email de cancelacion
        self.check_email_cancellation()
        
        #6. Comprobar email de actualizacion
        self.check_email_update()
        
        #7. Comprobar email de notificacion por parte del local
        self.check_email_notification()

    