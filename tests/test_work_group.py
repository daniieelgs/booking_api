import json
import unittest
from flask_testing import TestCase
from app import create_app, db
from tests import config_test, getUrl

ENDPOINT = 'work_group'

class TestWorkGroup(TestCase):
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

    def create_work_group(self):
        
        #Create locals
        localData = {
            "name": "Local-Test",
            "tlf": "123456789",
            "email": "email@test.com",
            "location": "Europe/Madrid"
        }
        responseLocal1 = self.client.post(getUrl('local'), data=json.dumps(localData), headers={'Authorization': f"Bearer {self.admin_token}"}, content_type='application/json')
        localData['email'] = "email2@test.com"
        responseLocal2 = self.client.post(getUrl('local'), data=json.dumps(localData), headers={'Authorization': f"Bearer {self.admin_token}"}, content_type='application/json')
        
        self.refresh_token1 = responseLocal1.json['refresh_token']
        self.refresh_token2 = responseLocal2.json['refresh_token']
        
        self.access_token1 = responseLocal1.json['access_token']
        self.access_token2 = responseLocal2.json['access_token']
        
        self.local_id1 = responseLocal1.json['local']['id']
        self.local_id2 = responseLocal2.json['local']['id']
        
        self.locals.append(self.local_id1)
        self.locals.append(self.local_id2)
        
        #Create work groups
        self.data2 = self.data.copy()
        self.data2['name'] = 'work group test 2'
        
        #Local 1
        response = self.client.post(getUrl(ENDPOINT), data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 401)

        response = self.client.post(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token1}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.work_group_post = dict(response.json)
        
        response = self.client.post(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token1}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 409) #Check if the name is already in use

        response = self.client.post(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token1}"}, data=json.dumps(self.data2), content_type='application/json')
        self.assertEqual(response.status_code, 201)

        #Local 2
        response = self.client.post(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token2}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 201)

        response = self.client.post(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token2}"}, data=json.dumps(self.data2), content_type='application/json')
        self.assertEqual(response.status_code, 201)

    def get_work_group(self):
        work_group_id = self.work_group_post['id']
        response = self.client.get(getUrl(ENDPOINT, work_group_id))
        self.assertEqual(response.status_code, 200)
        self.work_group_get = dict(response.json)
        _work_group_get = self.work_group_post.copy()
        _work_group_get.pop('datetime_created', None)
        _work_group_get.pop('datetime_updated', None)
        _work_group_get.pop('local_id', None)
        _work_group_get.pop('id', None)
        self.assertEqual(_work_group_get, self.data)


    def get_all_work_groups(self):
        #Local 1
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id1))
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(len(data), 2)
        
        #Local 2
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id2))
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(len(data), 2)

    def update_work_group(self):
        response = self.client.put(getUrl(ENDPOINT, self.work_group_post['id']), data=json.dumps(self.data2), content_type='application/json')
        self.assertEqual(response.status_code, 401)
        
        response = self.client.put(getUrl(ENDPOINT, self.work_group_post['id']), headers={'Authorization': f"Bearer {self.refresh_token1}"}, data=json.dumps(self.data2), content_type='application/json')
        self.assertEqual(response.status_code, 409) #Check if the name is already in use
        
        self.data2['name'] = 'work group test 3'
        response = self.client.put(getUrl(ENDPOINT, self.work_group_post['id']), headers={'Authorization': f"Bearer {self.refresh_token2}"}, data=json.dumps(self.data2), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        response = self.client.put(getUrl(ENDPOINT, self.work_group_post['id']), headers={'Authorization': f"Bearer {self.refresh_token1}"}, data=json.dumps(self.data2), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.work_group_put = dict(response.json)
        self.assertNotEqual(self.work_group_put['datetime_updated'], self.work_group_get['datetime_updated'])
        self.work_group_put.pop('datetime_updated', None)
        self.work_group_put.pop('name', None)
        self.work_group_get.pop('datetime_updated', None)
        self.work_group_get.pop('name', None)
        self.assertEqual(self.work_group_put, self.work_group_get)

    def delete_work_group(self):
        response = self.client.delete(getUrl(ENDPOINT, self.work_group_post['id']), headers={'Authorization': f"Bearer {self.refresh_token1}"}, content_type='application/json')
        self.assertEqual(response.status_code, 401)
        
        response = self.client.delete(getUrl(ENDPOINT, self.work_group_post['id']), headers={'Authorization': f"Bearer {self.access_token1}"}, content_type='application/json')
        self.assertEqual(response.status_code, 204)
        
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id1))
        self.assertEqual(len(response.json['work_groups']), 1)
        
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id2))
        self.assertEqual(len(response.json), 2)

    def test_integration_work_group(self):

        self.data = {
            "name": "work group test",
            "description": "work group description test",
        }

        #POST
        self.create_work_group()
        
        #GET
        self.get_work_group()
        self.get_all_work_groups()
        
        #PUT
        self.update_work_group()
        
        #DELETE
        self.delete_work_group()

if __name__ == '__main__':
    unittest.main()
