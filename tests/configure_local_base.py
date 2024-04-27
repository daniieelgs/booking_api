
import datetime
import json
from globals import WEEK_DAYS
from tests.config_test import getUrl


class LocalBase():
    
    def __init__(self, client, admin_token, assertEqual) -> None:
        self.client = client
        self.admin_token = admin_token
        self.assertEqual = assertEqual
        self.locals = []
    
    def create_local(self, booking_timeout, set_local_settings=True, set_smtp_settings=True):
        self.local = {
            "name": "Local-Test",
            "tlf": "123456789",
            "email": "email@test.com",
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
            "booking_timeout": booking_timeout
        }
        
        reset_time =  (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
        
        self.smtp_settings = [
            {   
                "host": "smtp-relay.brevo.com",
                "mail": "info@local.com",
                "max_send_per_day": 300,
                "max_send_per_month": 1000,
                "name": "config-1",
                "password": "0000000000000000000",
                "port": 587,
                "priority": 10,
                "reset_send_per_day": reset_time,
                "reset_send_per_month": reset_time,
                "send_per_day": 100,
                "send_per_month": 100,
                "user": "user@mail.com"
            },
            {
                "host": "smtp.sendgrid.net",
                "mail": "info@local.com",
                "max_send_per_day": 100,
                "name": "config-2",
                "password": "0000000000000000",
                "port": 587,
                "priority": 20,
                "reset_send_per_day": reset_time,
                "send_per_day": 10,
                "user": "apikey"
            },
        ]
        
        if set_smtp_settings: self.local_settings['smtp_settings'] = self.smtp_settings
        if set_local_settings: self.local['local_settings'] = self.local_settings
        
        r = self.client.post(getUrl('local'), data=json.dumps(self.local),  headers={'Authorization': f"Bearer {self.admin_token}"}, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        
        r = dict(r.json)
        
        self.refresh_token = r['refresh_token']
        self.access_token = r['access_token']
        self.local['id'] = r['local']['id']
        
        self.locals.append(r['local']['id'])
        
    def create_timetable(self):
        
        self.timetable = []
        
        for day in WEEK_DAYS:
            self.timetable.append({
                "opening_time": "10:00:00",
                "closing_time": "15:00:00",
                "weekday_short": day
            })
            self.timetable.append({
                "opening_time": "16:00:00",
                "closing_time": "20:00:00",
                "weekday_short": day
            })
        
        r = self.client.put(getUrl('timetable'), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(self.timetable), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        
    def create_work_group(self):
        self.work_groups = [
            {
                "name": "work group test 1",
                "description": "work group 1 description test",
            },
            {
                "name": "work group test 2",
                "description": "work group 2 description test",
            },
            {
                "name": "work group test 3",
                "description": "work group 3 description test",
            }
        ]
        
        for i in range(len(self.work_groups)):
            work_group = self.work_groups[i]
            r = self.client.post(getUrl('work_group'), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(work_group), content_type='application/json')
            self.assertEqual(r.status_code, 201)
            self.work_groups[i]['id'] = dict(r.json)['id']
        
    def create_service(self):
        
        
        self.services = []
        
        for i in range(len(self.work_groups)):
            id = self.work_groups[i]['id']
            
            services = [
                {
                    "name": "service test 1",
                    "description": "service 1 description test",
                    "duration": 30,
                    "price": 10,
                    "work_group": 1
                },
                {
                    "name": "service test 2",
                    "description": "service 2 description test",
                    "duration": 60,
                    "price": 20,
                    "work_group": 1
                },
                {
                    "name": "service test 3",
                    "description": "service 3 description test",
                    "duration": 90,
                    "price": 30,
                    "work_group": 1
                }
            ]
            
            for j in range(len(services)):
                services[j]['name'] = services[j]['name'] + f" - WG {id}"
                services[j]['work_group'] = id
                
                service = services[j]
                r = self.client.post(getUrl('service'), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(service), content_type='application/json')
                self.assertEqual(r.status_code, 201)
                services[j]['id'] = dict(r.json)['id']
                
                self.services.append(services[j])
                
            self.work_groups[i]['services'] = services
                        
    def create_worker(self):
        
        self.workers = [
            {
                "name": "worker test 1",
                "last_name": "worker surname 1",
                "work_groups": [self.work_groups[0]['id']]
            },
            {
                "name": "worker test 2",
                "last_name": "worker surname 2",
                "work_groups": [self.work_groups[0]['id'], self.work_groups[1]['id']]
            },
            {
                "name": "worker test 3",
                "last_name": "worker surname 3",
                "work_groups": [self.work_groups[0]['id']]
            }
        ]
        
        for i in range(len(self.workers)):
            worker = self.workers[i]
            r = self.client.post(getUrl('worker'), headers={'Authorization': f"Bearer {self.refresh_token}"}, data=json.dumps(worker), content_type='application/json')
            self.assertEqual(r.status_code, 201)
            self.workers[i]['id'] = dict(r.json)['id']
                        
            for wg_id in worker['work_groups']:
                
                index = None
                
                for j in range(len(self.work_groups)):
                    if self.work_groups[j]['id'] == wg_id:
                        if 'workers' not in self.work_groups[j]: self.work_groups[j]['workers'] = []
                        index = j
                        break
                                
                if index is not None:
                    workers = list(self.work_groups[index]['workers'])
                    workers.append(worker)
                    self.work_groups[index]['workers'] = workers
                    
    def configure_local(self, booking_timeout, set_local_settings=True, set_smtp_settings=True, set_timetable=True, set_work_groups=True, set_services=True, set_workers=True):
        self.create_local(booking_timeout, set_local_settings, set_smtp_settings)
        if set_timetable: self.create_timetable()
        if set_work_groups: self.create_work_group()
        if set_services: self.create_service()
        if set_workers: self.create_worker()

def configure(client, admin_token, assertEqual, booking_timeout=-1, set_local_settings=True, set_smtp_settings=True, set_timetable=True, set_work_groups=True, set_services=True, set_workers=True):
    lb = LocalBase(client, admin_token, assertEqual)
    lb.configure_local(booking_timeout, set_local_settings, set_smtp_settings, set_timetable, set_work_groups, set_services, set_workers)
    
    return lb
   