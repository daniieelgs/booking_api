# python -m unittest .\tests\test_booking.py

import datetime
import json
import time
import unittest
from flask_testing import TestCase
from app import create_app, db
from globals import CANCELLED_STATUS, CONFIRMED_STATUS, DONE_STATUS, PENDING_STATUS, WEEK_DAYS, DEBUG
from tests import ConfigTest, getUrl, setParams
from tests.configure_local_base import configure
from dateutil.relativedelta import relativedelta

ENDPOINT = 'booking'

BOOKING_TIMEOUT = 2

class TestEmail(TestCase):
    def create_app(self):
        self.config_test = ConfigTest(waiter_booking_status=BOOKING_TIMEOUT)
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
    
    def cancel_booking_admin(self, id, data = None, **params):
        return self.client.delete(setParams(getUrl(ENDPOINT, 'cancel', id), **params), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json') if data is None else self.client.delete(setParams(getUrl(ENDPOINT, id)), data=json.dumps(data), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json')
  
    def update_booking_admin(self, id, booking, **params):
        return self.client.put(setParams(getUrl(ENDPOINT, id), **params), data=json.dumps(booking), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json')
    
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
          
    def update_local_settings(self):
 
        data = self.local.local
        
        local_id = data.pop('id')
        
        r = self.client.put(getUrl('local'), data=json.dumps(data),  headers={'Authorization': f"Bearer {self.local.access_token}"}, content_type='application/json')
        
        self.assertEqual(r.status_code, 200)
        
        data['id'] = local_id
        
    def reset_smtp_config(self, send_per_day = 0, send_per_month = 0, max_send_per_day = 300, max_send_per_month = 1000, reset_send_per_day = 1, reset_send_per_month = 1, edit_configs = []):
                
        def get_reset_time(reset):            
            return (datetime.datetime.now() + datetime.timedelta(days=reset)).strftime("%Y-%m-%dT00:00:00")
        
        if len(edit_configs) == 0:
            n = len(self.local.local_settings['smtp_settings'])
            edit_configs = list(range(n))
        
        for i in range(len(self.local.local_settings['smtp_settings'])):
            
            if i not in edit_configs: continue
            
            smtp = self.local.local_settings['smtp_settings'][i]
            
            smtp['send_per_day'] = send_per_day
            smtp['send_per_month'] = send_per_month
        
            smtp['max_send_per_day'] = max_send_per_day
            smtp['max_send_per_month'] = max_send_per_month
        
            smtp['reset_send_per_day'] = get_reset_time(reset_send_per_day)
            smtp['reset_send_per_month'] = get_reset_time(reset_send_per_month)
            
            

        self.update_local_settings()
        
    def create_intern_booking(self, booking = None):
        
        if not booking: booking = self.booking
        
        post_booking = self.post_booking(booking)
        
        self.assertEqual(post_booking.status_code, 201)
        
        response = post_booking.json
        
        self._intern_booking = response
        
        return response
    
    def cancel_intern_booking(self):
        
        if not hasattr(self, '_intern_booking') or 'session_token' not in self._intern_booking: return
        
        self.cancel_booking(self._intern_booking['session_token'])
        
        self._intern_booking = None
        
    def check_email_booking(self, email, value, booking_id = None):
        
        if booking_id is None: booking_id = self._intern_booking['booking']['id']
        
        booking_admin = self.get_booking_admin(booking_id)
        self.assertEqual(booking_admin.status_code, 200)
        booking_response = booking_admin.json
        
        self.assertEqual(booking_response[email], value)
        
    def recreate_intern_booking(self, booking = None):
        self.cancel_intern_booking()
        return self.create_intern_booking(booking=booking)  
          
    def patch_local(self, data):
        return self.client.patch(getUrl('local'), data=json.dumps(data), headers={'Authorization': f"Bearer {self.local.access_token}"}, content_type='application/json')
    
    def enable_send_email_confirm(self, timeout = 0):
        data = {
            "local_settings": {
                "booking_timeout": timeout
            }
        }
        
        r = self.patch_local(data)
        self.assertEqual(r.status_code, 200)
        
    def disable_send_email_confirm(self):
        self.enable_send_email_confirm(-1)

    def check_email(self):
        post_booking = self.post_booking(self.booking)
                
        self.assertEqual(post_booking.status_code, 201)
        
        response = post_booking.json
        
        self.assertEqual(response['booking']['status']['status'], PENDING_STATUS)
        self.assertEqual(response['email_confirm'], True)
        
        self.check_email_booking('email_confirm', True, response['booking']['id'])
        
    
    def check_control_email(self):
        #2.1. Control de envio de emails por dia y mes
        
        send_day_pre = self.get_local_settings()['smtp_settings'][0]['send_per_day']
        send_month_pre = self.get_local_settings()['smtp_settings'][0]['send_per_month']
        
        response = self.recreate_intern_booking()
        
        self.assertEqual(response['email_confirm'], True)
        
        send_day_post = self.get_local_settings()['smtp_settings'][0]['send_per_day']
        send_month_post = self.get_local_settings()['smtp_settings'][0]['send_per_month']
        
        self.assertEqual(send_day_post, send_day_pre + 1)
        self.assertEqual(send_month_post, send_month_pre + 1)
        
        self.check_email_booking('email_confirm', True)        
                
        #2.2. Comprobar reseteos

        send_day_pre = 300
        send_month_pre = 300

        self.reset_smtp_config(send_per_day=send_day_pre, send_per_month=send_month_pre, reset_send_per_day=-1, reset_send_per_month=1, edit_configs=[0])
                
        self.recreate_intern_booking()#+1
                
        settings = self.get_local_settings()
        
        send_day_post = settings['smtp_settings'][0]['send_per_day']
        send_month_post = settings['smtp_settings'][0]['send_per_month']
        reset_day = settings['smtp_settings'][0]['reset_send_per_day']
        
        self.assertEqual(send_day_post, 2)
        self.assertEqual(send_month_post, send_month_pre + 2)
        
        self.check_email_booking('email_confirm', True)
        
        self.assertEqual(reset_day, (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00"))
                                
        response = self.recreate_intern_booking()#+1
        
        send_day_post = self.get_local_settings()['smtp_settings'][0]['send_per_day']
        send_month_post = self.get_local_settings()['smtp_settings'][0]['send_per_month']
        
        self.assertEqual(send_day_post, 4)
        self.assertEqual(send_month_post, send_month_pre + 4)
        
        self.reset_smtp_config(send_per_day=2, send_per_month=50, reset_send_per_day=1, reset_send_per_month=-1, edit_configs=[0])
                        
        self.check_email_booking('email_confirm', True)
                        
        self.recreate_intern_booking()#+1
        
        send_day_post = self.get_local_settings()['smtp_settings'][0]['send_per_day']
        send_month_post = self.get_local_settings()['smtp_settings'][0]['send_per_month']
        reset_month = self.get_local_settings()['smtp_settings'][0]['reset_send_per_month']
        
        self.assertEqual(send_day_post, 4)
        self.assertEqual(send_month_post, 2)
        
        self.assertEqual(reset_month, (datetime.datetime.now() - datetime.timedelta(days=1) + relativedelta(months=+1)).strftime("%Y-%m-%dT00:00:00"))
                
        self.check_email_booking('email_confirm', True)
                
        #2.3. Comprobar limite de emails en una configuracion (dia/mes)
                
            #Limite por dia
                
        self.local.local_settings['smtp_settings'][0]['send_per_day'] = self.local.local_settings['smtp_settings'][0]['max_send_per_day']
        
        self.update_local_settings()
        
        send_day_pre0 = self.get_local_settings()['smtp_settings'][0]['send_per_day']
        send_day_pre1 = self.get_local_settings()['smtp_settings'][1]['send_per_day']
        send_month_pre0 = self.get_local_settings()['smtp_settings'][0]['send_per_month']
        
        self.recreate_intern_booking()#+1
        
        self.assertEqual(response['email_confirm'], True)
          
        settings = self.get_local_settings()
                
        self.assertEqual(settings['smtp_settings'][0]['send_per_day'], send_day_pre0)
        self.assertEqual(settings['smtp_settings'][0]['send_per_month'], send_month_pre0)                

        self.assertEqual(settings['smtp_settings'][1]['send_per_day'], send_day_pre1 + 2)
        
        self.check_email_booking('email_confirm', True)
        
            #Limite por mes
        
        self.local.local_settings['smtp_settings'][0]['send_per_month'] = self.local.local_settings['smtp_settings'][0]['max_send_per_month']
        self.local.local_settings['smtp_settings'][0]['send_per_day'] = 0
        self.local.local_settings['smtp_settings'][0]['reset_send_per_day'] = self.local.local_settings['smtp_settings'][0]['reset_send_per_month'] = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
                
        self.update_local_settings()
        
        settings = self.get_local_settings()
        
        send_month_pre0 = settings['smtp_settings'][0]['send_per_month']
        send_day_pre0 = settings['smtp_settings'][0]['send_per_day']
        send_day_pre1 = settings['smtp_settings'][1]['send_per_day']
        
        response = self.recreate_intern_booking()#+1
        
        self.assertEqual(response['email_confirm'], True)
        
        
        settings = self.get_local_settings()
        
        self.assertEqual(settings['smtp_settings'][0]['send_per_month'], send_month_pre0)
        self.assertEqual(settings['smtp_settings'][0]['send_per_day'], send_day_pre0)
        self.assertEqual(settings['smtp_settings'][1]['send_per_day'], send_day_pre1 + 2)
                
        self.check_email_booking('email_confirm', True)
                
        #2.4. Comprobar limite de emails en todas las configuraciones
        
        self.local.local_settings['smtp_settings'][0]['send_per_day'] = self.local.local_settings['smtp_settings'][0]['max_send_per_day']
        self.local.local_settings['smtp_settings'][1]['send_per_day'] = self.local.local_settings['smtp_settings'][1]['max_send_per_day']

        self.update_local_settings()
        
        settings = self.get_local_settings()
        
        send_day_pre0 = settings['smtp_settings'][0]['send_per_day']
        send_day_pre1 = settings['smtp_settings'][1]['send_per_day']
        
        response = self.recreate_intern_booking()#+1
        
        self.assertEqual(response['email_confirm'], False)
        
        settings = self.get_local_settings()
        
        self.assertEqual(settings['smtp_settings'][0]['send_per_day'], send_day_pre0)
        self.assertEqual(settings['smtp_settings'][1]['send_per_day'], send_day_pre1)
                
        self.check_email_booking('email_confirm', False)
                
        #2.5. Comprobar limite de emails en todas las configuraciones y reseteos
    
            #Resetear por dia
    
        self.local.local_settings['smtp_settings'][0]['reset_send_per_day'] = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
        
        self.update_local_settings()
        
        settings = self.get_local_settings()
        
        response = self.recreate_intern_booking()#+1
        
        self.assertEqual(response['email_confirm'], False)
        
        settings = self.get_local_settings()
                
            #Resetear por mes
            
        self.local.local_settings['smtp_settings'][0]['reset_send_per_month'] = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
        
        self.update_local_settings()
        
        settings = self.get_local_settings()
        
        response = self.recreate_intern_booking()#+1
        
        self.assertEqual(response['email_confirm'], True)
        
        settings = self.get_local_settings()
        
        self.assertEqual(settings['smtp_settings'][0]['send_per_day'], 2)
        self.assertEqual(settings['smtp_settings'][0]['send_per_month'], 2)
        
        self.check_email_booking('email_confirm', True)
        
    def check_cancel_confirm_email(self):
        #3.1 Confirmacion automatica de reserva
        
        self.reset_smtp_config(send_per_day=300, max_send_per_day=300)
        
        response = self.recreate_intern_booking()
        
        self.assertEqual(response['email_confirm'], False)
        self.assertEqual(response['booking']['status']['status'], CONFIRMED_STATUS)
        
        self.check_email_booking('email_confirm', False)
        
        #3.2. Cancelacion automatica. Sin confirmar reserva
        
        self.reset_smtp_config()
        
        booking3_2 = self.recreate_intern_booking()
        
        self.check_email_booking('email_confirm', True, booking3_2['booking']['id'])
                
        #3.3. Confirmando reserva
        
        self.booking['datetime_init'] = booking3_2['booking']['datetime_end']
        
        booking3_3 = self.create_intern_booking()
        
        self.check_email_booking('email_confirm', True, booking3_3['booking']['id'])
        
        r = self.confirm_booking(booking3_3['session_token'])
        self.assertEqual(r.status_code, 200)
        
        time.sleep(BOOKING_TIMEOUT)
        
        booking3_2 = self.get_booking(booking3_2['session_token']).json
        self.assertEqual(booking3_2['status']['status'], CANCELLED_STATUS)
        
        self.check_email_booking('email_cancelled', True, booking3_2['id'])
        
        booking3_3 = self.get_booking(booking3_3['session_token']).json
        self.assertEqual(booking3_3['status']['status'], CONFIRMED_STATUS)
        
        self.check_email_booking('email_confirmed', True, booking3_3['id'])
            
    def check_email_confirmation(self):
        
        self.reset_smtp_config()
        
        response = self.recreate_intern_booking()
        
        settings = self.get_local_settings()
        
        send_day_pre = settings['smtp_settings'][0]['send_per_day']
        send_month_pre = settings['smtp_settings'][0]['send_per_month']
        
        r = self.confirm_booking(response['session_token'])
        self.assertEqual(r.status_code, 200)
        
        settings = self.get_local_settings()
        
        send_day_post = settings['smtp_settings'][0]['send_per_day']
        send_month_post = settings['smtp_settings'][0]['send_per_month']
        
        self.assertEqual(send_day_post, send_day_pre + 1)
        self.assertEqual(send_month_post, send_month_pre + 1)
            
        self.check_email_booking('email_confirmed', True)
            
    def check_email_cancellation(self):
        self.reset_smtp_config()
        
        response = self.recreate_intern_booking()
        
        settings = self.get_local_settings()
        
        send_day_pre = settings['smtp_settings'][0]['send_per_day']
        send_month_pre = settings['smtp_settings'][0]['send_per_month']
        
        r = self.cancel_booking(response['session_token'])
        self.assertEqual(r.status_code, 204)
        
        settings = self.get_local_settings()
        
        send_day_post = settings['smtp_settings'][0]['send_per_day']
        send_month_post = settings['smtp_settings'][0]['send_per_month']
        
        self.assertEqual(send_day_post, send_day_pre + 1)
        self.assertEqual(send_month_post, send_month_pre + 1)
        
        self.check_email_booking('email_cancelled', True)
    
    def check_email_update(self):
        
        self.reset_smtp_config()
        
        response = self.recreate_intern_booking()
        
        settings = self.get_local_settings()
        send_day_pre = settings['smtp_settings'][0]['send_per_day']
        send_month_pre = settings['smtp_settings'][0]['send_per_month']
        
        r = self.update_booking(response['session_token'], self.booking)
        self.assertEqual(r.status_code, 200)
        
        settings = self.get_local_settings()
        send_day_post = settings['smtp_settings'][0]['send_per_day']
        send_month_post = settings['smtp_settings'][0]['send_per_month']
        
        self.assertEqual(send_day_post, send_day_pre + 1)
        self.assertEqual(send_month_post, send_month_pre + 1)
        
        self.check_email_booking('email_updated', True)
    
    def check_email_notification(self):
        #7.1. Creando reserva
        
        self.reset_smtp_config()
        
        settings = self.get_local_settings()
        
        send_day_pre = settings['smtp_settings'][0]['send_per_day']
        send_month_pre = settings['smtp_settings'][0]['send_per_month']
        
        booking_admin0 = self.post_booking_local(self.booking, force = True)
        self.assertEqual(booking_admin0.status_code, 201)
        booking_response0 = booking_admin0.json
        
        settings = self.get_local_settings()
        
        send_day_post = settings['smtp_settings'][0]['send_per_day']
        send_month_post = settings['smtp_settings'][0]['send_per_month']
        
        self.assertEqual(send_day_post, send_day_pre)
        self.assertEqual(send_month_post, send_month_pre)
        
        self.check_email_booking('email_confirm', False, booking_response0['id'])
        self.check_email_booking('email_confirmed', False, booking_response0['id'])
        
        booking_admin = self.post_booking_local(self.booking, force = True, notify = True)
        self.assertEqual(booking_admin.status_code, 201)
        booking_response = booking_admin.json
        
        settings = self.get_local_settings()
        
        send_day_post = settings['smtp_settings'][0]['send_per_day']
        send_month_post = settings['smtp_settings'][0]['send_per_month']
        
        self.assertEqual(send_day_post, send_day_pre + 1)
        self.assertEqual(send_month_post, send_month_pre + 1)
        
        self.check_email_booking('email_confirm', False, booking_response['id'])
        self.check_email_booking('email_confirmed', True, booking_response['id'])
        
        #7.2. Actualizando reserva
        
        self.booking['new_status'] = 'C'
        
        settings = self.get_local_settings()

        send_day_pre = settings['smtp_settings'][0]['send_per_day']
        send_month_pre = settings['smtp_settings'][0]['send_per_month']
        
        booking_update = self.update_booking_admin(booking_response['id'], self.booking, force=True)
        self.assertEqual(booking_update.status_code, 200)
        
        send_day_post = settings['smtp_settings'][0]['send_per_day']
        send_month_post = settings['smtp_settings'][0]['send_per_month']
        
        self.assertEqual(send_day_post, send_day_pre)
        self.assertEqual(send_month_post, send_month_pre)
        
        self.check_email_booking('email_updated', False, booking_response0['id'])
        
        booking_update = self.update_booking_admin(booking_response['id'], self.booking, force=True, notify=True)
        self.assertEqual(booking_update.status_code, 200)
        
        settings = self.get_local_settings()
        
        send_day_post = settings['smtp_settings'][0]['send_per_day']
        send_month_post = settings['smtp_settings'][0]['send_per_month']
        
        self.assertEqual(send_day_post, send_day_pre + 1)
        self.assertEqual(send_month_post, send_month_pre + 1)
        
        self.check_email_booking('email_updated', True, booking_response['id'])
        
        self.booking.pop('new_status')
        
        #7.3. Cancelando reserva
        
        settings = self.get_local_settings()

        send_day_pre = settings['smtp_settings'][0]['send_per_day']
        send_month_pre = settings['smtp_settings'][0]['send_per_month']
        
        booking_cancel = self.cancel_booking_admin(booking_response0['id'], data=None)
        self.assertEqual(booking_cancel.status_code, 204)
        
        settings = self.get_local_settings()
        
        send_day_post = settings['smtp_settings'][0]['send_per_day']
        send_month_post = settings['smtp_settings'][0]['send_per_month']
        self.assertEqual(send_day_post, send_day_pre)
        self.assertEqual(send_month_post, send_month_pre)
        
        self.check_email_booking('email_cancelled', False, booking_response0['id'])
        
        booking_cancel = self.cancel_booking_admin(booking_response['id'], data=None, notify=True)
        self.assertEqual(booking_cancel.status_code, 204)
        
        settings = self.get_local_settings()
        
        send_day_post = settings['smtp_settings'][0]['send_per_day']
        send_month_post = settings['smtp_settings'][0]['send_per_month']
        self.assertEqual(send_day_post, send_day_pre + 1)
        self.assertEqual(send_month_post, send_month_pre + 1)
                  
        self.check_email_booking('email_cancelled', True, booking_response['id'])
              
    def check_booking_status(self):
        response = self.create_intern_booking()
        
        self.assertEqual(response['booking']['status']['status'], PENDING_STATUS)
        self.assertEqual(response['email_confirm'], True)
        
        session_token = response['session_token']
        booking_id = response['booking']['id']
        
        get_booking = self.get_booking(session_token)
        self.assertEqual(get_booking.status_code, 200)
        response = get_booking.json
        
        self.assertEqual(response['status']['status'], PENDING_STATUS)
        
        booking_admin = self.get_booking_admin(booking_id)
        self.assertEqual(booking_admin.status_code, 200)
        response = booking_admin.json
        
        self.assertEqual(response['email_confirm'], True)
        
        confirm_booking = self.confirm_booking(session_token)
        self.assertEqual(confirm_booking.status_code, 200)
        response = confirm_booking.json
        
        self.assertEqual(response['status']['status'], CONFIRMED_STATUS)
        
        booking_admin = self.get_booking_admin(booking_id)
        self.assertEqual(booking_admin.status_code, 200)
        response = booking_admin.json
        
        self.assertEqual(response['email_confirmed'], True)
        
        self.cancel_booking(session_token)
        
        #Desactivar el envio de emails de confirmacion
        
        self.disable_send_email_confirm()
        
        response = self.create_intern_booking()
        
        self.assertEqual(response['booking']['status']['status'], CONFIRMED_STATUS)
        self.assertEqual(response['email_confirm'], False)
        
        session_token = response['session_token']
        booking_id = response['booking']['id']
        
        get_booking = self.get_booking(session_token)
        self.assertEqual(get_booking.status_code, 200)
        response = get_booking.json
        
        self.assertEqual(response['status']['status'], CONFIRMED_STATUS)
        
        booking_admin = self.get_booking_admin(booking_id)
        self.assertEqual(booking_admin.status_code, 200)
        response = booking_admin.json
        
        self.assertEqual(response['email_confirm'], False)
        self.assertEqual(response['email_confirmed'], True)
        
        confirm_booking = self.confirm_booking(session_token)
        self.assertEqual(confirm_booking.status_code, 409)
        
        self.cancel_booking(session_token)
        
        self.enable_send_email_confirm()
        
    
    def check_booking_confirm_mail_disabled(self):
        
        self.reset_smtp_config()
        self.disable_send_email_confirm()
        
        settings = self.get_local_settings()
        
        send_day_pre = settings['smtp_settings'][0]['send_per_day']
        send_month_pre = settings['smtp_settings'][0]['send_per_month']
        
        response = self.create_intern_booking()
        
        self.assertEqual(response['booking']['status']['status'], CONFIRMED_STATUS)
        
        self.check_email_booking('email_confirm', False)
        self.check_email_booking('email_confirmed', True)
        
        settings = self.get_local_settings()
        
        send_day_post = settings['smtp_settings'][0]['send_per_day']
        send_month_post = settings['smtp_settings'][0]['send_per_month']
        
        self.assertEqual(send_day_post, send_day_pre + 1)
        self.assertEqual(send_month_post, send_month_pre + 1)
        
        self.cancel_booking(response['session_token'])
        
        get_booking = self.get_booking(response['session_token'])
        self.assertEqual(get_booking.status_code, 200)
        response = get_booking.json
        
        self.assertEqual(response['status']['status'], CANCELLED_STATUS)
        self.check_email_booking('email_cancelled', True)
        
        #Limite de correos:
        
        self.reset_smtp_config(send_per_day=300, max_send_per_day=300)
        
        response = self.create_intern_booking()
        
        self.assertEqual(response['booking']['status']['status'], CONFIRMED_STATUS)
        self.assertEqual(response['email_confirm'], False)
        
        self.cancel_booking(response['session_token'])
        
        get_booking = self.get_booking(response['session_token'])
        self.assertEqual(get_booking.status_code, 200)
        response = get_booking.json
        
        self.assertEqual(response['status']['status'], CANCELLED_STATUS)
        self.check_email_booking('email_cancelled', False)
        
        self.enable_send_email_confirm()
        self.reset_smtp_config()
                  
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
            
        #4. Comprobar email de confirmacion
        self.check_email_confirmation()
        
        #5. Comprobar email de cancelacion
        self.check_email_cancellation()
        
        #6. Comprobar email de actualizacion
        self.check_email_update()
        
        #7. Comprobar email de notificacion por parte del local
        self.check_email_notification()
        
        #8. Comprobar estados de reservas
        self.check_booking_status()
        
        #9. Comprobar no envio de emails para confirmacion
        self.check_booking_confirm_mail_disabled()
        
        #3. Comprobar cancelacion/confirmacion automatica de emails
        self.check_cancel_confirm_email()
    