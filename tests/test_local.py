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

    def tearDown(self):

        db.session.remove()
        db.drop_all()

    def test_integration_local(self):

        #GET
        data = {
            "name": "Local-Test",
            "tlf": "123456789",
            "email": "email@test.com",
            "address": "Test Address",
            "postal_code": "98765",
            "village": "Test Village",
            "province": "Test Province",
            "location": "ES"
        }

        response_post = self.client.post(getUrl(ENDPOINT), data=json.dumps(data), content_type='application/json')
        self.assertEqual(response_post.status_code, 201)
        
        refresh_token = response_post.json['refresh_token']
        local_post = dict(response_post.json['local'])
        
        
        #POST
        response_get = self.client.get(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {refresh_token}"})
        self.assertEqual(response_get.status_code, 200)
        
        local_get = dict(response_get.json['local'])
        local_get.pop('password_generated', None)
        local_get.pop('datetime_created', None)
        local_post.pop('password_generated', None)
        local_post.pop('datetime_created', None)

        self.assertEqual(local_get, self.local_post)
                

if __name__ == '__main__':
    unittest.main()
