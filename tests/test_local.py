# python -m unittest .\tests\test_local.py

import json
import unittest
from flask_testing import TestCase
from app import create_app, db
from globals import MIN_TIMEOUT_CONFIRM_BOOKING
from tests import config_test, getUrl

ENDPOINT = 'local'

class TestLocal(TestCase):
    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):

        db.create_all()
        config_test.config(db = db)
        self.admin_token = config_test.ADMIN_TOKEN

    def tearDown(self):

        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)

    def put_local(self, local, token):
        return self.client.put(getUrl(ENDPOINT), data=json.dumps(local), headers={'Authorization': f"Bearer {token}"}, content_type='application/json')

    def patch_local(self, local, token):
        return self.client.patch(getUrl(ENDPOINT), data=json.dumps(local), headers={'Authorization': f"Bearer {token}"}, content_type='application/json')

    def post_local(self, local):
        return self.client.post(getUrl(ENDPOINT), data=json.dumps(local), headers={'Authorization': f"Bearer {self.admin_token}"}, content_type='application/json')

    def del_local(self, token):
        return self.client.delete(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.admin_token}"}, content_type='application/json')

    def create_local(self):
        response_post = self.client.post(getUrl(ENDPOINT), data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response_post.status_code, 401)
        response_post = self.client.post(getUrl(ENDPOINT), data=json.dumps(self.data),  headers={'Authorization': f"Bearer {self.admin_token}"}, content_type='application/json')
        self.assertEqual(response_post.status_code, 201)
        response_post_repited = self.client.post(getUrl(ENDPOINT), data=json.dumps(self.data), headers={'Authorization': f"Bearer {self.admin_token}"}, content_type='application/json')
        self.assertEqual(response_post_repited.status_code, 409)
        
        self.refresh_token = response_post.json['refresh_token']
        self.access_token = response_post.json['access_token']
        self.local_post = dict(response_post.json['local'])
        self.password_generated = self.local_post.pop('password_generated', None)
        
        self.locals.append(dict(response_post.json['local'])['id'])

    def get_local(self):
        response_get = self.client.get(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"})
        self.assertEqual(response_get.status_code, 200)
        
        self.local_get = dict(response_get.json)

        self.assertEqual(self.local_get, self.local_post)
        
    def get_public_local(self):
        response_get = self.client.get(getUrl(ENDPOINT, self.local_post['id']))
        self.assertEqual(response_get.status_code, 200)

    def update_local(self):
        self.data['name'] = 'Local-Test-2'
        self.data['village'] = 'Test Village 2'
        self.data['location'] = 'FR'
        
        response_put = self.client.put(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response_put.status_code, 401)
        response_put = self.client.put(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.access_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response_put.status_code, 200)
        
        self.local_get['name'] = self.data['name']
        self.local_get['village'] = self.data['village']
        self.local_get['location'] = self.data['location']
        
        local_put = dict(response_put.json)
        self.assertNotEqual(local_put['local']['datetime_updated'], self.local_get['datetime_updated'])
        local_put['local'].pop('datetime_updated', None)
        self.local_get.pop('datetime_updated', None)
        self.assertEqual(local_put['local'], self.local_get)

    def delete_local(self):
        response = self.client.post(getUrl(ENDPOINT, 'login'), data=json.dumps({'email': self.data['email'], 'password': self.password_generated}), content_type='application/json')
        
        self.refresh_token = response.json['refresh_token']
        self.access_token = response.json['access_token']

        response_delete = self.client.delete(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, content_type='application/json')
        self.assertEqual(response_delete.status_code, 401)
        response_delete = self.client.delete(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.access_token}"}, content_type='application/json')
        self.assertEqual(response_delete.status_code, 204)
        
        
        response_get = self.client.get(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"})
        self.assertEqual(response_get.status_code, 401)

    def refresh(self):
        response_refresh = self.client.post(getUrl(ENDPOINT, 'refresh'), content_type='application/json')
        self.assertEqual(response_refresh.status_code, 401)
        
        response_refresh = self.client.post(getUrl(ENDPOINT, 'refresh'), headers={'Authorization': f"Bearer {self.refresh_token}"}, content_type='application/json')
        self.assertEqual(response_refresh.status_code, 200)
        
        self.refresh_token = response_refresh.json['refresh_token']
        self.assertEqual('access_token' in response_refresh.json, False)

    def login_local(self):
        response_login = self.client.post(getUrl(ENDPOINT, 'login'), data=json.dumps({'email': self.data['email'], 'password': self.password_generated}), content_type='application/json')
        self.assertEqual(response_login.status_code, 200)

    def logout_local(self):     
        response = self.client.post(getUrl(ENDPOINT, 'logout'), headers={'Authorization': f"Bearer {self.refresh_token}"}, content_type='application/json')
        self.assertEqual(response.status_code, 204)
        
        response = self.client.get(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, content_type='application/json')
        self.assertEqual(response.status_code, 401)
        
    def logout_all_local(self):
        refresh_token1 = self.client.post(getUrl(ENDPOINT, 'login'), data=json.dumps({'email': self.data['email'], 'password': self.password_generated}), content_type='application/json').json['refresh_token']
        refresh_token2 = self.client.post(getUrl(ENDPOINT, 'login'), data=json.dumps({'email': self.data['email'], 'password': self.password_generated}), content_type='application/json').json['refresh_token']
        response = self.client.post(getUrl(ENDPOINT, 'logout/all'), headers={'Authorization': f"Bearer {refresh_token1}"}, content_type='application/json')
        self.assertEqual(response.status_code, 204)
        
        response = self.client.get(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {refresh_token2}"}, content_type='application/json')
        self.assertEqual(response.status_code, 401)


    def create_settings(self):
        
        self.maxDiff = None
        
        self.data['local_settings'] = self.local_settings
        
        #Configuracion basica
        response_post = self.post_local(self.data)

        self.assertEqual(response_post.status_code, 201)

        self.local = dict(response_post.json)
        
        self.local['local']['local_settings'].pop('smtp_settings')
        
        self.assertEqual(self.local['local']['local_settings'], self.local_settings)

        r = self.del_local(self.local['access_token'])
        self.assertEqual(r.status_code, 204)

        #Test booking_tiemout
        self.data['local_settings']['booking_timeout'] = MIN_TIMEOUT_CONFIRM_BOOKING - 1
        response_post = self.post_local(self.data)

        print("response_post:\n", self.local)

        self.locals.append(self.local['local']['id'])
        
    def update_settings(self):
        pass

    def test_integration_settings(self):
        
        self.data = {
            "name": "Local-Test-Settings",
            "tlf": "123456789",
            "email": "settings@test.com",
            "address": "Test Address",
            "postal_code": "98765",
            "village": "Test Village",
            "province": "Test Province",
            "location": "Europe/Madrid"
        }
        
        
        self.local_settings = {
            "website": "https://www.website.com",
            "instagram": "https://www.instagram.com/local_ig",
            "facebook": "https://www.facebook.com/local_fb",
            "twitter": "https://www.twitter.com/local_tw",
            "whatsapp": "https://api.whatsapp.com/message/0000000000",
            "linkedin": "https://www.linkedin.com/local_lkd",
            "tiktok": "https://www.tiktok.com/local_tk",
            "maps": "https://www.google.com/maps/place/local",
            "email_contact": "contact@local.com",
            "phone_contact": "+34 000000000",
            "email_support": "support@local.com",
            "domain": "local.com",
            "confirmation_link": "https://www.local.com/confirm/{token}",
            "cancel_link": "https://www.local.com/cancel/{token}",
            "booking_timeout": 10
        }
        
        
        
        self.create_settings()
        self.update_settings()

    def test_integration_local(self):

        self.data = {
            "name": "Local-Test",
            "tlf": "123456789",
            "email": "email@test.com",
            "address": "Test Address",
            "postal_code": "98765",
            "village": "Test Village",
            "province": "Test Province",
            "location": "Europe/Madrid"
        }
    
        #POST
        self.create_local()
        
        #GET
        self.get_local()
        self.get_public_local()
        
        #PUT
        self.update_local()
                
        #Refresh Token
        self.refresh()
        
        #Login
        self.login_local()
        
        #Logout
        self.logout_local()        
        
        #Logout All
        self.logout_all_local()
        
        #DELETE
        self.delete_local()

if __name__ == '__main__':
    unittest.main()
