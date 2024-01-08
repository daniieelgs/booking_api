import json
import unittest
from flask_testing import TestCase
from app import create_app, db
from tests import config_test, getUrl

ENDPOINT = 'worker'

class TestWorker(TestCase):
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

    def create_worker(self):
        
        #Create local
        localData = {
            "name": "Local-Test",
            "tlf": "123456789",
            "email": "email@test.com",
            "location": "ES"
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
        
        #Create workers
        response = self.client.post(getUrl(ENDPOINT), data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 401)
        
        response = self.client.post(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 404)
        
        self.data['work_groups'] = [self.wg1['id']]
        response = self.client.post(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.worker_post1 = dict(response.json)
        
        self.data['name'] = 'Worker Test 2'
        self.data['work_groups'] = [self.wg1['id'], self.wg2['id']]
        response = self.client.post(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.worker_post2 = dict(response.json)


    def get_worker(self):
        worker_id1 = self.worker_post1['id']
        response = self.client.get(getUrl(ENDPOINT, worker_id1))
        self.assertEqual(response.status_code, 200)
        self.worker_get = dict(response.json)
        
        #Workers Work Groups
        response = self.client.get(getUrl(ENDPOINT, worker_id1, 'work_group'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(dict(response.json)['work_groups']), 1)
        
        worker_id2 = self.worker_post2['id']
        response = self.client.get(getUrl(ENDPOINT, worker_id2, 'work_group'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(dict(response.json)['work_groups']), 2)
        self.worker_get2 = dict(response.json)

        #Work Groups Workers
        response = self.client.get(getUrl('work_group', self.wg1['id'], 'workers'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(dict(response.json)['workers']), 2)

    def get_all_workers(self):
        #Workers
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id))
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(len(data), 2)
        
        #Workers Work Groups
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id, 'work_group'))
        self.assertEqual(response.status_code, 200)
        data = response.json['workers']
        
        for worker in data:
            if worker['id'] == self.worker_post1['id']: self.assertEqual(len(worker['work_groups']), 1)
            elif worker['id'] == self.worker_post2['id']: self.assertEqual(len(worker['work_groups']), 2)

        #Work Groups Workers
        response = self.client.get(getUrl('work_group', 'local', self.local_id, 'workers'))
        self.assertEqual(response.status_code, 200)
        data = response.json['work_groups']
        
        for wg in data:
            if wg['id'] == self.wg1['id']: self.assertEqual(len(wg['workers']), 2)
            elif wg['id'] == self.wg2['id']: self.assertEqual(len(wg['workers']), 1)

    def update_worker(self):
        
        self.data['work_groups'] = []
        
        response = self.client.put(getUrl(ENDPOINT, self.worker_post2['id']), data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 401)
        
        response = self.client.put(getUrl(ENDPOINT, self.worker_post2['id']), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 404)
        
        self.data['work_groups'] = [self.wg1['id']]
        
        response = self.client.put(getUrl(ENDPOINT, self.worker_post2['id']), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        self.worker_put = dict(response.json)
        self.assertNotEqual(self.worker_put['datetime_updated'], self.worker_post2['datetime_updated'])
        
        self.assertEqual(len(self.worker_put['work_groups']), 1)
        self.assertEqual(self.worker_put['work_groups'][0]['id'], self.wg1['id'])

        self.worker_put.pop('datetime_updated', None)
        self.worker_put.pop('work_groups', None)
        self.worker_post2.pop('datetime_updated', None)
        self.worker_post2.pop('work_groups', None)
        self.assertEqual(self.worker_put, self.worker_post2)

    def delete_worker(self):
        response = self.client.delete(getUrl(ENDPOINT, self.worker_post1['id']), headers={'Authorization': f"Bearer {self.refresh_token}"}, content_type='application/json')
        self.assertEqual(response.status_code, 401)
        
        response = self.client.delete(getUrl(ENDPOINT, self.worker_post1['id']), headers={'Authorization': f"Bearer {self.access_token}"}, content_type='application/json')
        self.assertEqual(response.status_code, 204)
        
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id))
        self.assertEqual(len(response.json['workers']), 1)

    def test_integration_work_group(self):

        self.data = {
            "name": "Worker Test",
            "last_name": "Worker Test Last Name",
            "email": "worker@example.com",
            "tlf": "123456789",
            "work_groups": []
        }

        #POST
        self.create_worker()
        
        #GET
        self.get_worker()
        self.get_all_workers()
        
        #PUT
        self.update_worker()
        
        #DELETE
        self.delete_worker()

if __name__ == '__main__':
    unittest.main()
