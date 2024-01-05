import json
import unittest
from flask_testing import TestCase
from app import create_app, db
from tests import config_test, getUrl

ENDPOINT = 'local'

class TestLocal(TestCase):
    def create_app(self):
        app = create_app(config_test)
        return app

    def setUp(self):

        db.create_all()
        config_test.config(db = db)
        self.admin_token = config_test.ADMIN_TOKEN

    def tearDown(self):

        db.session.remove()
        db.drop_all()

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
        self.assertNotEqual(local_put['datetime_updated'], self.local_get['datetime_updated'])
        local_put.pop('datetime_updated', None)
        self.local_get.pop('datetime_updated', None)
        self.assertEqual(local_put, self.local_get)

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


    def test_integration_local(self):

        self.data = {
            "name": "Local-Test",
            "tlf": "123456789",
            "email": "email@test.com",
            "address": "Test Address",
            "postal_code": "98765",
            "village": "Test Village",
            "province": "Test Province",
            "location": "ES"
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
