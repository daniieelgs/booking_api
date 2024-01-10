import json
import unittest
from flask_testing import TestCase
from app import create_app, db
from tests import config_test, getUrl

ENDPOINT = 'service'

class TestService(TestCase):
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

    def create_service(self):
        
        #Create local
        localData = {
            "name": "Local-Test",
            "tlf": "123456789",
            "email": "email@test.com",
            "location": "Europe/Madrid"
        }
        responseLocal = self.client.post(getUrl('local'), data=json.dumps(localData), headers={'Authorization': f"Bearer {self.admin_token}"}, content_type='application/json')
                
        self.refresh_token = responseLocal.json['refresh_token']
        
        self.access_token = responseLocal.json['access_token']
                
        self.local_id = responseLocal.json['local']['id']
                
        #Create work groups
         
        dataWG = {
            "name": "work group test",
            "description": "work group description test",
        }
        
        dataWG2 = dataWG.copy()
        dataWG2['name'] = 'work group test 2'
        
        response = self.client.post(getUrl('work_group'), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(dataWG), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.wg1 = dict(response.json)

        response = self.client.post(getUrl('work_group'), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(dataWG2), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.wg2 = dict(response.json)
        
        #Create services
        response = self.client.post(getUrl(ENDPOINT), data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 401)
        
        response = self.client.post(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 404)
        
        self.data['work_group'] = self.wg1['id']
        response = self.client.post(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        print(response.json)
        self.assertEqual(response.status_code, 201)
        self.service_post = dict(response.json)

        response = self.client.post(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 409)
        self.data['name'] = 'Service Test 2'
        response = self.client.post(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 201)


    def get_service(self):
        service_id = self.service_post['id']
        response = self.client.get(getUrl(ENDPOINT, service_id))
        self.assertEqual(response.status_code, 200)
        self.service_get = dict(response.json)
        self.assertEqual(self.service_get['work_group']['id'], self.wg1['id'])

        #Work Groups Services
        response = self.client.get(getUrl('work_group', self.wg1['id'], 'services'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(dict(response.json)['services']), 2)

    def get_all_services(self):
        #Services
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id))
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(len(data), 2)

        #Work Groups Services
        response = self.client.get(getUrl('work_group', 'local', self.local_id, 'services'))
        self.assertEqual(response.status_code, 200)
        data = response.json['work_groups']
        
        for wg in data:
            if wg['id'] == self.wg1['id']: self.assertEqual(len(wg['services']), 2)
            elif wg['id'] == self.wg2['id']: self.assertEqual(len(wg['services']), 0)

    def update_service(self):
        
        self.data['work_group'] = 0
        
        response = self.client.put(getUrl(ENDPOINT, self.service_post['id']), data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 401)
        
        response = self.client.put(getUrl(ENDPOINT, self.service_post['id']), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 404)
        
        self.data['work_group'] = self.wg1['id']
        
        response = self.client.put(getUrl(ENDPOINT, self.service_post['id']), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 409)
        
        self.data['work_group'] = self.wg2['id']
        
        response = self.client.put(getUrl(ENDPOINT, self.service_post['id']), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        self.service_put = dict(response.json)
        
        self.assertNotEqual(self.service_put['datetime_updated'], self.service_get['datetime_updated'])
        
        self.assertEqual(self.service_put['work_group']['id'], self.wg2['id'])

        self.service_put.pop('datetime_updated', None)
        self.service_put.pop('work_group', None)
        self.service_put.pop('name', None)
        self.service_get.pop('datetime_updated', None)
        self.service_get.pop('work_group', None)
        self.service_get.pop('name', None)
        self.assertEqual(self.service_put, self.service_get)

    def delete_service(self):
        response = self.client.delete(getUrl(ENDPOINT, self.service_post['id']), headers={'Authorization': f"Bearer {self.refresh_token}"}, content_type='application/json')
        self.assertEqual(response.status_code, 401)
        
        response = self.client.delete(getUrl(ENDPOINT, self.service_post['id']), headers={'Authorization': f"Bearer {self.access_token}"}, content_type='application/json')
        self.assertEqual(response.status_code, 204)
        
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id))
        self.assertEqual(len(response.json['services']), 1)
    
    def delete_all_services(self):
        response = self.client.delete(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, content_type='application/json')
        self.assertEqual(response.status_code, 401)
        
        response = self.client.delete(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.access_token}"}, content_type='application/json')
        self.assertEqual(response.status_code, 204)

        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id))
        self.assertEqual(len(response.json['services']), 0)

    def test_integration_work_group(self):

        self.data = {
            "name": "Service Test",
            "description": "Service description test",
            "duration": 60,
            "price": 19.99,
            "work_group": 0
        }

        #POST
        self.create_service()
        
        #GET
        self.get_service()
        self.get_all_services()
        
        #PUT
        self.update_service()
        
        #DELETE
        self.delete_service()
        self.delete_all_services()

if __name__ == '__main__':
    unittest.main()
