import datetime
import json
import unittest
from flask_testing import TestCase
from app import create_app, db
from globals import WEEK_DAYS
from tests import config_test, getUrl, setParams

ENDPOINT = 'booking'

class TestBooking(TestCase):
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
        self.local = {
            "name": "Local-Test",
            "tlf": "123456789",
            "email": "email@test.com",
            "address": "Test Address",
            "postal_code": "98765",
            "village": "Test Village",
            "province": "Test Province",
            "location": "ES"
        }
        
        r = self.client.post(getUrl('local'), data=json.dumps(self.local),  headers={'Authorization': f"Bearer {self.admin_token}"}, content_type='application/json')
        self.assertEqual(r.status_code, 201)
        
        r = dict(r.json)
        
        self.refresh_token = r['refresh_token']
        self.access_token = r['access_token']
        self.local['id'] = r['local']['id']
        
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
        print(r.json)
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
                    
               
    def configure_local(self):
        self.create_local()
        self.create_timetable()
        self.create_work_group()
        self.create_service()
        self.create_worker()
    
    def post_booking(self, booking):
        return self.client.post(getUrl(ENDPOINT, 'local', self.local['id']), data=json.dumps(booking), content_type='application/json')
    
    def cancel_booking(self, session):
        return self.client.delete(setParams(getUrl(ENDPOINT), session=session), content_type='application/json')
    
    def missingData(self, _booking):
        booking = _booking.copy()
        
        #Fecha en pasado
        booking['datetime_init'] = "2020-01-01 13:00:00"
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
        
        booking['datetime_init'] = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        #Falta de datos: correo
        email = booking.pop('client_email')
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 422)
        booking['client_email'] = email
        
        #Falta de datos: servicios
        booking['services_ids'] = []
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 404)
    
    def outOfTimetable(self, _booking):
        booking = _booking.copy()
        
        #Antes de horario
        time = (datetime.datetime.strptime(self.timetable[0]['opening_time'], "%H:%M:%S") - datetime.timedelta(minutes=10)).strftime("%H:%M:%S")
        data = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        booking['datetime_init'] = f"{data} {time}"
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
        
        #Despues de horario
        time = (datetime.datetime.strptime(self.timetable[1]['closing_time'], "%H:%M:%S") - datetime.timedelta(minutes=10)).strftime("%H:%M:%S")
        data = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        booking['datetime_init'] = f"{data} {time}"
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
        
        #Entre horarios
        time = (datetime.datetime.strptime(self.timetable[0]['closing_time'], "%H:%M:%S") + datetime.timedelta(minutes=10)).strftime("%H:%M:%S")
        data = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        booking['datetime_init'] = f"{data} {time}"
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
    
    def workerNotAvailable(self, _booking):
        
        def filterWorkers(n):
            wg = [wg for wg in self.work_groups if ('workers' not in wg and n == 0) or ('workers' in wg and len(wg['workers']) == n)]
            return wg[0] if len(wg) > 0 else None

        booking = _booking.copy()

        #Servicio que no tiene trabajadores
        service_id = filterWorkers(0)['services'][0]['id']
        booking['services_ids'] = [service_id]
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
        
        #Trabajador que no tiene el servicio
        booking['worker_id'] = self.workers[0]['id']
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
        booking.pop('worker_id')
        
        #Servicio que tiene un trabajador: Reserva 1
        service_id = filterWorkers(1)['services'][0]['id']
        booking['services_ids'] = [service_id]
        r = self.post_booking(booking)
        booking_response = dict(r.json)
        self.assertEqual(r.status_code, 201)
        
        #Servicio que tiene un trabajador: Reserva 2
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
        
        booking['worker_id'] = booking_response['booking']['worker']['id'] #Seleccionando el trabajador de la reserva anterior
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
        
        #Servicio que tiene un trabajador: Reserva 2 (despues de cancelar reserva 1)
        r = self.cancel_booking(booking_response['session_token'])
        self.assertEqual(r.status_code, 204)
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        
        #Servicio que tiene un trabajador: Reserva 2 (despues de reserva 1)
        booking['datetime_init'] = booking_response['booking']['datetime_end']
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
    
    def create_bookings(self):
            
        self.bookings = []
        
        time = (datetime.datetime.strptime(self.timetable[0]['opening_time'], "%H:%M:%S")).strftime("%H:%M:%S")
        data = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        booking = {
            "client_name": "Client Test",
            "client_tlf": "123456789",
            "client_email": "client@example.com",
            "datetime_init": f"{data} {time}",
            "services_ids": [self.services[0]['id']]
        }
    
        #TEST 0: Falta de datos y datos incorrectos
        self.missingData(booking)

        #TEST 1: Fuera de horario
        self.outOfTimetable(booking)
    
        #TEST 2: Trabajador/es no disponible
        self.workerNotAvailable(booking)
    
        
    def test_integration_booking(self):
        
        self.configure_local()
        self.create_bookings()
        
        pass