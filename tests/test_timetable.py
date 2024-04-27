import json
import unittest
from flask_testing import TestCase
from sqlalchemy import text
from app import create_app, db
from models.weekday import WeekdayModel
from tests import config_test, getUrl

ENDPOINT = 'timetable'

class TestTimetable(TestCase):
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

    def create_timetable(self):
        
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
                
        self.locals.append(self.local_id)
                
        new_timetable = {
                "opening_time": "13:00:00",
                "closing_time": "15:00:00",
                "weekday_short": "fr"
        }
        
        self.data.append(new_timetable)
        
        response = self.client.put(getUrl(ENDPOINT), data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 401)
        
        response = self.client.put(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 409)
        
        self.data.pop()
        new_timetable['opening_time'] = '22:00:00'
        new_timetable['closing_time'] = '21:00:00'
        self.data.append(new_timetable)
        response = self.client.put(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 409)
        
        self.data.pop()

        response = self.client.put(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 200)

    def get_timetable(self):
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id, 'week', 'fr'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 2)
        
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id, 'week', 'SU'))
        self.assertEqual(response.status_code, 204)
        
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id, 'week', 'MK'))
        self.assertEqual(response.status_code, 404)

    def get_all_timetables(self):
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id, 'week'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 3)

    def update_timetable(self):
        
        response = self.client.put(getUrl(ENDPOINT), data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 401)
        
        response = self.client.put(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        new_timetable = {
                "opening_time": "13:00:00",
                "closing_time": "15:00:00",
                "weekday_short": "fr"
        }
        self.data.append(new_timetable)
        response = self.client.put(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 409)
        
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id, 'week'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 3)
        
        self.data.pop()

        self.data[-1]['closing_time'] = '18:00:00'
        self.data[-1]['weekday_short'] = 'mk'
        response = self.client.put(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 404)
        
        self.data[-1]['weekday_short'] = 'fr'
        response = self.client.put(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.data), content_type='application/json')
        self.assertEqual(response.status_code, 200)

    def delete_timetable(self):
        response = self.client.delete(getUrl(ENDPOINT, 'week', 'mo'), content_type='application/json')
        self.assertEqual(response.status_code, 401)
        
        response = self.client.delete(getUrl(ENDPOINT, 'week', 'mo'), headers={'Authorization': f"Bearer {self.refresh_token}"}, content_type='application/json')
        self.assertEqual(response.status_code, 204)
        
        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id, 'week', 'mo'))
        self.assertEqual(response.status_code, 204)
    
    def delete_all_timetables(self):
        response = self.client.put(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps([]), content_type='application/json')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(getUrl(ENDPOINT, 'local', self.local_id, 'week'))
        self.assertEqual(len(response.json), 0)

    def test_integration_work_group(self):

        self.data = [
            {
                "opening_time": "08:00:00",
                "closing_time": "17:00:00",
                "weekday_short": "MO"
            },
            {
                "opening_time": "08:00:00",
                "closing_time": "13:00:00",
                "weekday_short": "fr"
            },
            {
                "opening_time": "15:00:00",
                "closing_time": "20:00:00",
                "weekday_short": "fr"
            }
        ]


        #PUT
        self.create_timetable()
        
        #GET
        self.get_timetable()
        self.get_all_timetables()
        
        #PUT
        self.update_timetable()
        
        #DELETE
        self.delete_timetable()
        self.delete_all_timetables()

if __name__ == '__main__':
    unittest.main()
