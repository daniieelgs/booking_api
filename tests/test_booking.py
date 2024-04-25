# python -m unittest .\tests\test_booking.py

import datetime
import json
import time
import unittest
from flask_testing import TestCase
from app import create_app, db
from globals import CANCELLED_STATUS, CONFIRMED_STATUS, DONE_STATUS, PENDING_STATUS, WEEK_DAYS, DEBUG
from tests import config_test, getUrl, setParams
from tests.configure_local_base import configure

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
        config_test.drop(self.local.locals)
        
    def configure_local(self):
        self.local = configure(self.client, self.admin_token, self.assertEqual, set_smtp_settings=False, set_local_settings=False)

    def post_booking_admin(self, booking):
        return self.client.post(getUrl(ENDPOINT, 'admin'), data=json.dumps(booking), headers={'Authorization': f"Bearer {self.admin_token}"}, content_type='application/json')
   
    def post_booking(self, booking):
        return self.client.post(getUrl(ENDPOINT, 'local', self.local.local['id']), data=json.dumps(booking), content_type='application/json')
    
    def post_booking_local(self, booking, **params):
        return self.client.post(setParams(getUrl(ENDPOINT), **params), data=json.dumps(booking), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json')
    
    def cancel_booking(self, session, data = None):
        return self.client.delete(setParams(getUrl(ENDPOINT), session=session), content_type='application/json') if data is None else self.client.delete(setParams(getUrl(ENDPOINT), session=session), data=json.dumps(data), content_type='application/json')
    
    def cancel_booking_admin(self, id, data = None):
        return self.client.delete(setParams(getUrl(ENDPOINT, 'cancel', id)), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json') if data is None else self.client.delete(setParams(getUrl(ENDPOINT, id)), data=json.dumps(data), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json')
  
    def update_booking_admin(self, id, booking):
        return self.client.put(getUrl(ENDPOINT, id), data=json.dumps(booking), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, content_type='application/json')
    
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
        time = (datetime.datetime.strptime(self.local.timetable[0]['opening_time'], "%H:%M:%S") - datetime.timedelta(minutes=10)).strftime("%H:%M:%S")
        data = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        booking['datetime_init'] = f"{data} {time}"
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
        
        #Despues de horario
        time = (datetime.datetime.strptime(self.local.timetable[1]['closing_time'], "%H:%M:%S") - datetime.timedelta(minutes=10)).strftime("%H:%M:%S")
        data = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        booking['datetime_init'] = f"{data} {time}"
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
        
        #Entre horarios
        time = (datetime.datetime.strptime(self.local.timetable[0]['closing_time'], "%H:%M:%S") + datetime.timedelta(minutes=10)).strftime("%H:%M:%S")
        data = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        booking['datetime_init'] = f"{data} {time}"
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
    
    def filterWgbyNworkers(self, n, ge = False):
        wg = [wg for wg in self.local.work_groups if ('workers' not in wg and n == 0) or ('workers' in wg and len(wg['workers']) == n) or (ge and 'workers' in wg and len(wg['workers']) >= n)]
        return wg[0] if len(wg) > 0 else None
    
    def filterWorkersByNwg(self, n):
        return [w for w in self.local.workers if ('work_groups' not in w and n == 0) or len(w['work_groups']) == n]
    
    def workerNotAvailable(self, _booking):
        

        booking = _booking.copy()

        #Servicio que no tiene trabajadores
        service_id = self.filterWgbyNworkers(0)['services'][0]['id']
        booking['services_ids'] = [service_id]
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
        
        #Trabajador que no tiene el servicio
        booking['worker_id'] = self.local.workers[0]['id']
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
        booking.pop('worker_id')
        
        #Servicio que tiene un trabajador: Reserva 1
        service_id = self.filterWgbyNworkers(1)['services'][0]['id']
        booking['services_ids'] = [service_id]
        r = self.post_booking(booking)
        booking_response = dict(r.json)
        print('Booking response:', booking_response)
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
        r1 = self.post_booking(booking)
        self.assertEqual(r1.status_code, 201)
        
        #Servicio que tiene un trabajador: Reserva 2 (despues de reserva 1)
        booking['datetime_init'] = booking_response['booking']['datetime_end']
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        r = self.cancel_booking(dict(r.json)['session_token'])
        self.assertEqual(r.status_code, 204)
        
        r = self.cancel_booking(dict(r1.json)['session_token'])
        self.assertEqual(r.status_code, 204)
    
    def checkBooking(self, _booking):
        
        booking = _booking.copy()
        
        totalDuration = 0
        totalPrice = 0
        
        for service_id in booking['services_ids']:
            service = [service for service in self.local.services if service['id'] == service_id][0]
            totalDuration += service['duration']
            totalPrice += service['price']
        
        booking['services_ids'].append(booking['services_ids'][0])
        
        #Crear reserva
        r = self.post_booking(booking)
        response = dict(r.json)
        self.assertEqual(r.status_code, 201)
        
        #Comprobar datos:
        booking_response = response['booking']
            #Datos de cliente
        self.assertEqual(booking_response['client_name'], booking['client_name'].strip().title())
        self.assertEqual(booking_response['client_email'], booking['client_email'])
        self.assertEqual(booking_response['datetime_init'].replace('T', ' '), booking['datetime_init'])
            #Obviar servicios repetidos
        self.assertEqual(len(booking_response['services']), len(booking['services_ids']) - 1)
            #Tiempo de duracion
        self.assertEqual(booking_response['datetime_end'].replace('T', ' '), (datetime.datetime.strptime(booking['datetime_init'], "%Y-%m-%d %H:%M:%S") + datetime.timedelta(minutes=totalDuration)).strftime("%Y-%m-%d %H:%M:%S"))
            #Precio total
        self.assertEqual(booking_response['total_price'], totalPrice)
            #Estado
        self.assertEqual(booking_response['status']['status'], CONFIRMED_STATUS)
                
        self.assertEqual(response['timeout'], config_test.waiter_booking_status if config_test.waiter_booking_status else None)
    
        #Obtener reserva
        session = response['session_token']
        
        r = self.get_booking(session)
        response = dict(r.json)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(response['id'], booking_response['id'])
        self.assertEqual(response['client_email'], booking_response['client_email'])
        self.assertEqual(booking_response['status']['status'], CONFIRMED_STATUS) #PENDING
        
        #Confirmar reserva #TODO test
        # r = self.confirm_booking(session)
        # response = dict(r.json)
        # self.assertEqual(r.status_code, 200)
        # self.assertEqual(response['id'], booking_response['id'])
        # self.assertEqual(response['status']['status'], CONFIRMED_STATUS)
        
        # r = self.get_booking(session)
        # response = dict(r.json)
        # self.assertEqual(response['status']['status'], CONFIRMED_STATUS)
        
        #Volver a confirmar reserva
        r = self.confirm_booking(session)
        self.assertEqual(r.status_code, 409)
        
        #Cancelar reserva
        data = {
            "comment": "Cancelled test"
        }
        r = self.cancel_booking(session, data = data)
        self.assertEqual(r.status_code, 204)
        r = self.get_booking(session)
        response = dict(r.json)
        self.assertEqual(response['status']['status'], CANCELLED_STATUS)
        self.assertEqual(response['comment'], data['comment'])
        
        #Confirmar reserva
        r = self.confirm_booking(session)
        self.assertEqual(r.status_code, 409)     
        
        #Obtener reserva despues de ser terminado
        booking['datetime_init'] = "2020-01-01 13:00:00"
        booking['worker_id'] = response['worker']['id']
        r = self.post_booking_admin(booking)
        self.assertEqual(r.status_code, 201)
        
        session = dict(r.json)['session_token']
        
        r = self.get_booking(session)
        self.assertEqual(r.status_code, 401)
        
        #Comprobar caducidad del token
        
        # timetable = self.local.timetable
        timetable = []
        
        for day in WEEK_DAYS:
            timetable.append({
                "opening_time": "00:00:00",
                "closing_time": "23:59:59",
                "weekday_short": day
            })
            
        r = self.client.put(getUrl('timetable'), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, data=json.dumps(timetable), content_type='application/json')    
        self.assertEqual(r.status_code, 200)
        
        time_wait = 2
        
        datetime_init = (datetime.datetime.now() + datetime.timedelta(seconds=time_wait)).__str__().split('.')[0] #TODO
        
        pre_datetime_init = booking['datetime_init']
        
        booking['datetime_init'] = datetime_init
        
        post_booking = self.post_booking(booking)
        self.assertEqual(post_booking.status_code, 201)
        
        get_booking = self.get_booking(dict(post_booking.json)['session_token'])
        self.assertEqual(get_booking.status_code, 200)
        
        time.sleep(time_wait)
        get_booking = self.get_booking(dict(post_booking.json)['session_token'])
        self.assertEqual(get_booking.status_code, 403)
        
        cancel_booking = self.cancel_booking(dict(post_booking.json)['session_token'])
        self.assertEqual(cancel_booking.status_code, 403)
        
        booking['datetime_init'] = pre_datetime_init
        
        cancel_booking_admin = self.cancel_booking_admin(dict(post_booking.json)['booking']['id'])
        self.assertEqual(cancel_booking_admin.status_code, 204)
                
        timetable = self.local.timetable
        r = self.client.put(getUrl('timetable'), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, data=json.dumps(timetable), content_type='application/json')
        self.assertEqual(r.status_code, 200)
    
    def checkUpdateBooking(self, _booking):
        booking = _booking.copy()
        
        response = dict(self.post_booking(booking).json)
        response_booking = response['booking']
        session = response['session_token']    
        
    
        #Actualizar reserva sin cambiar datos
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 200)
        response = dict(r.json)
        self.assertNotEqual(response_booking['datetime_updated'], response['datetime_updated'])
        du = response.pop('datetime_updated')
        response_booking.pop('datetime_updated')
        self.assertEqual(response_booking, response)
        
        #Actualizar con datos justos
        data = {
            "client_name": "Client name test",
        }
        r = self.patch_booking(session, data)
        self.assertEqual(r.status_code, 200)
        response2 = dict(r.json)
        self.assertNotEqual(response2['datetime_updated'], du)
        self.assertEqual(response2['client_name'], data['client_name'].strip().title())
        self.assertEqual(response2['worker']['id'], response['worker']['id'])
        self.assertEqual(response2['datetime_init'], response['datetime_init'])
        
        #Actualizar con datos justos desde local
        data = {
            "new_status": PENDING_STATUS,
        }
        r = self.patch_booking_admin(response['id'], data)
        self.assertEqual(r.status_code, 200)
        response2 = dict(r.json)
        self.assertNotEqual(response2['status']['status'], response['status']['status'])
        self.assertEqual(response2['status']['status'], data['new_status'])
        self.assertEqual(response2['worker']['id'], response['worker']['id'])
        self.assertEqual(response2['datetime_init'], response['datetime_init'])
        
        
        #Tiempo en pasado
        booking['datetime_init'] = "2020-01-01 13:00:00"
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 409)
        booking = _booking.copy()
        
        #Falta de datos: correo
        email = booking.pop('client_email')
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 422)
        booking['client_email'] = email
        
        #Falta de datos: servicios
        booking['services_ids'] = []
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 404)
    
        #Cambiar a un trabajador que no tiene el servicio
        worker = self.local.workers[1] #Trabaja en WG 1 y 2
        service = self.local.work_groups[2-1]['services'][0] #Servicio de WG 2
        booking['worker_id'] = worker['id']
        booking['services_ids'] = [service['id']]
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 200)
        
        worker = self.local.workers[0] #No trabaja en WG 2
        booking['worker_id'] = worker['id']
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 409)
        
        #Cambiar servicio a uno que no tiene trabajadores
        
        service = self.filterWgbyNworkers(0)['services'][0] #Servicio sin trabajadores
        booking['services_ids'] = [service['id']]
        booking.pop('worker_id')
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 409)
        
        #Cambiar servicio a uno que tiene un trabajador
        service = self.filterWgbyNworkers(2, ge = True)['services'][0]
        booking['services_ids'] = [service['id']]
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 200)
        
        booking['worker_id'] = dict(r.json)['worker']['id'] #Comprobar que puedo seleccionar el trabajador que ya tiene aplicado
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 200)
        
        #Cambiar a un trabajador ocupado
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
        worker_id = booking.pop('worker_id')
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        worker_id2 = dict(r.json)['booking']['worker']['id']
        booking['worker_id'] = worker_id
        _session = dict(r.json)['session_token']
        r = self.update_booking(_session, booking)
        self.assertEqual(r.status_code, 409)

        #Cambiar a trabajador ocupado (despues de cancelar reserva anterior)

        booking.pop('worker_id')        
        r = self.post_booking(booking)
        _session2 = dict(r.json)['session_token']
        self.assertEqual(r.status_code, 201)
        booking['worker_id'] = worker_id2
        r = self.update_booking(_session2, booking)
        self.assertEqual(r.status_code, 409)
        
        self.assertEqual(self.cancel_booking(_session).status_code, 204)
        
        r = self.update_booking(_session2, booking)
        self.assertEqual(r.status_code, 200)
        
        self.assertEqual(self.cancel_booking(_session2).status_code, 204)
        
        #Cambiar hora fuera de horario: Antes de horario
                
        time = (datetime.datetime.strptime(self.local.timetable[0]['opening_time'], "%H:%M:%S") - datetime.timedelta(minutes=10)).strftime("%H:%M:%S")
        data = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        booking['datetime_init'] = f"{data} {time}"
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 409)
        
        #Cambiar hora fuera de horario: Despues de horario
        
        time = (datetime.datetime.strptime(self.local.timetable[0]['closing_time'], "%H:%M:%S") - datetime.timedelta(minutes=10)).strftime("%H:%M:%S")
        booking['datetime_init'] = f"{data} {time}"
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 409)
        
        #Cambiar servicio a uno de diferente work group definiendo trabajador
        
        booking['worker_id'] = worker_id
        service = self.filterWgbyNworkers(1)['services'][0]
        booking['services_ids'] = [service['id']]
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 409)
                
        #Combinar servicios de diferentes work group
        
        booking['services_ids'] = [self.local.work_groups[0]['services'][0]['id'], self.local.work_groups[1]['services'][0]['id']]
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 409)
                
        #Cambiar servicio a uno de diferente duracion y que salga de horario
        booking.pop('worker_id')
        service30 = self.local.services[0] #Servicio de 30 minutos
        service60 = self.local.services[1] #Servicio de 60 minutos
        booking['services_ids'] = [service30['id']]
        time = (datetime.datetime.strptime(self.local.timetable[0]['closing_time'], "%H:%M:%S") - datetime.timedelta(minutes=service30['duration'])).strftime("%H:%M:%S") 
        booking['datetime_init'] = f"{data} {time}"
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 200)
        
        booking['services_ids'] = [service60['id']] #Cambio a servicio de 60 minutos
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 409)
        
        #Cambiar servicio a uno de diferente duracion y que el trabajador no este disponible
        
        booking['services_ids'] = [service30['id']] #Cambio a servicio de 30 minutos
        time = (datetime.datetime.strptime(self.local.timetable[0]['opening_time'], "%H:%M:%S")).strftime("%H:%M:%S")
        booking['datetime_init'] = f"{data} {time}"
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 200)
        
        time = (datetime.datetime.strptime(self.local.timetable[0]['opening_time'], "%H:%M:%S") + datetime.timedelta(minutes=service30['duration'] + 10)).strftime("%H:%M:%S")  #Hora para cuando termine la reserva anterior
        booking['datetime_init'] = f"{data} {time}"
        booking['worker_id'] = dict(r.json)['worker']['id'] #Aplicamos el mismo trabajador
        r = self.post_booking(booking) #Creamos nueva reserva
        _session = dict(r.json)['session_token']
        self.assertEqual(r.status_code, 201)
        
        booking['services_ids'] = [service60['id']] #Cambio a servicio de 60 minutos
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 409)
        
        #Cambiar servicio a uno de diferente duracion y que sea posible
    
        worker_id = booking.pop('worker_id')
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(dict(r.json)['worker']['id'], worker_id)
        
        self.assertEqual(self.cancel_booking(_session).status_code, 204)
    
        #Actualizar servicio despues de ser cancelado
        r = self.cancel_booking(session)
        self.assertEqual(r.status_code, 204)
        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 409)
        
        #Actualizar servicio despues de ser acabado
        booking['datetime_init'] = "2020-01-01 13:00:00"
        booking['worker_id'] = worker_id
        r = self.post_booking_admin(booking)
        self.assertEqual(r.status_code, 201)
        
        session = dict(r.json)['session_token']

        r = self.update_booking(session, booking)
        self.assertEqual(r.status_code, 401)
        
    def checkListBooking(self, _booking):
        booking = _booking.copy()
        
        self.bookings = []
        
        self.worker_bookings = {}
        self.name_clients = {}
        self.email_clients = {}
        self.tlf_clients = {}
        
        def register_booking(r):
            worker_id = dict(r.json)['booking']['worker']['id']
            if worker_id in self.worker_bookings: self.worker_bookings[worker_id] += 1 
            else: self.worker_bookings[worker_id] = 1
            
            name = dict(r.json)['booking']['client_name']
            if name in self.name_clients: self.name_clients[name] += 1 
            else: self.name_clients[name] = 1
            
            email = dict(r.json)['booking']['client_email']
            if email in self.email_clients: self.email_clients[email] += 1
            else: self.email_clients[email] = 1
            
            tlf = dict(r.json)['booking']['client_tlf']
            if tlf in self.tlf_clients: self.tlf_clients[tlf] += 1
            else: self.tlf_clients[tlf] = 1
        
        #Crear reserva
        #Mismo dia. Mismo horario
        booking['client_name'] = "Client Test 1"
        booking['client_email'] = "test1@example.com"
        booking['client_tlf'] = "123456789"
        
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        register_booking(r)
        
        
        booking['client_name'] = "Client Test 2"
        booking['client_email'] = "test2@example.com"
        booking['client_tlf'] = "123456289"
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        register_booking(r)
        
        booking['client_name'] = "Client Test 3"
        booking['client_email'] = "test3@example.com"
        booking['client_tlf'] = "123456389"
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        register_booking(r)
                
        self.bookings.append({
            "datetime_init": booking['datetime_init'],
            "datetime_end": dict(r.json)['booking']['datetime_end'],
            "number": 3
        })
        
        #Mismo dia. Diferente horario
        booking['client_name'] = "Client Test 4"
        booking['client_email'] = "test4@example.com"
        booking['client_tlf'] = "123456489"
        booking['datetime_init'] = (datetime.datetime.strptime(booking['datetime_init'], "%Y-%m-%d %H:%M:%S") + datetime.timedelta(minutes=120)).strftime("%Y-%m-%d %H:%M:%S")
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        register_booking(r)
        
        self.bookings.append({
            "datetime_init": booking['datetime_init'],
            "datetime_end": dict(r.json)['booking']['datetime_end'],
            "number": 1
        })
        
        booking['client_name'] = "Client Test 1"
        booking['client_email'] = "test1@example.com"
        booking['client_tlf'] = "123456189"
        booking['datetime_init'] = (datetime.datetime.strptime(booking['datetime_init'], "%Y-%m-%d %H:%M:%S") + datetime.timedelta(minutes=360)).strftime("%Y-%m-%d %H:%M:%S")
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        register_booking(r)
        
        self.bookings.append({
            "datetime_init": booking['datetime_init'],
            "datetime_end": dict(r.json)['booking']['datetime_end'],
            "number": 1
        })
        
        booking['client_name'] = "Client Test 2"
        booking['client_email'] = "test2@example.com"
        booking['client_tlf'] = "123456289"
        booking['datetime_init'] = (datetime.datetime.strptime(booking['datetime_init'], "%Y-%m-%d %H:%M:%S") + datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        register_booking(r)
        
        self.bookings.append({
            "datetime_init": booking['datetime_init'],
            "datetime_end": dict(r.json)['booking']['datetime_end'],
            "number": 1
        })
        
        #Diferente dia.
        booking['client_name'] = "Client Test 5"
        booking['client_email'] = "test5@example.com"
        booking['client_tlf'] = "123456589"
        booking['datetime_init'] = (datetime.datetime.strptime(booking['datetime_init'], "%Y-%m-%d %H:%M:%S") + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        register_booking(r)
        
        self.bookings.append({
            "datetime_init": booking['datetime_init'],
            "datetime_end": dict(r.json)['booking']['datetime_end'],
            "number": 1
        })
        
        booking['client_name'] = "Client Test 2"
        booking['client_email'] = "test2@example.com"
        booking['client_tlf'] = "123456289"
        booking['datetime_init'] = (datetime.datetime.strptime(booking['datetime_init'], "%Y-%m-%d %H:%M:%S") + datetime.timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        register_booking(r)
        
        self.bookings.append({
            "datetime_init": booking['datetime_init'],
            "datetime_end": dict(r.json)['booking']['datetime_end'],
            "number": 1
        })
        
        #Testear listado de reservas
        #Listar reservas del mismo dia
        r = self.get_bookings(date = self.bookings[0]['datetime_init'].split(' ')[0])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json['bookings']), 6)
                
        #Lista reservas en horario especifico
        r = self.get_bookings(datetime_init = self.bookings[0]['datetime_init'], datetime_end = self.bookings[0]['datetime_end'].replace('T', ' '))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json['bookings']), self.bookings[0]['number'])
        
        #Listar reservas varios dias
        r = self.get_bookings(datetime_init = self.bookings[0]['datetime_init'], datetime_end = self.bookings[-1]['datetime_end'].replace('T', ' '))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json['bookings']), 8)
        
    def checkListFilterBooking(self):
        
        #Listar reservas por trabajador
        for k, v in self.worker_bookings.items():
            r = self.get_bookings(datetime_init = self.bookings[0]['datetime_init'], datetime_end = self.bookings[-1]['datetime_end'].replace('T', ' '), worker_id = k)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(len(r.json['bookings']), v)
        
    def checkListFilterDataClientBooking(self):
        
        for k, v in self.name_clients.items():
            r = self.get_bookings_admin(datetime_init = self.bookings[0]['datetime_init'], datetime_end = self.bookings[-1]['datetime_end'].replace('T', ' '), name = k, status = f"{PENDING_STATUS},{CONFIRMED_STATUS}")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(len(r.json['bookings']), v)
        
        for k, v in self.email_clients.items():
            r = self.get_bookings_admin(datetime_init = self.bookings[0]['datetime_init'], datetime_end = self.bookings[-1]['datetime_end'].replace('T', ' '), email = k, status = f"{PENDING_STATUS},{CONFIRMED_STATUS}")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(len(r.json['bookings']), v)
        
        for k, v in self.tlf_clients.items():
            r = self.get_bookings_admin(datetime_init = self.bookings[0]['datetime_init'], datetime_end = self.bookings[-1]['datetime_end'].replace('T', ' '), tlf = k, status = f"{PENDING_STATUS},{CONFIRMED_STATUS}")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(len(r.json['bookings']), v)
        
    def checkListFilterStatusBooking(self):
        r = self.get_bookings_admin(datetime_init = self.bookings[0]['datetime_init'], datetime_end = self.bookings[-1]['datetime_end'].replace('T', ' '), status = f"{PENDING_STATUS},{CONFIRMED_STATUS}")
        self.assertEqual(r.status_code, 200)
        
        for booking in r.json['bookings']:
            self.assertIn(booking['status']['status'], [PENDING_STATUS, CONFIRMED_STATUS])
            
        r = self.get_bookings_admin(datetime_init = self.bookings[0]['datetime_init'], datetime_end = self.bookings[-1]['datetime_end'].replace('T', ' '), status = CANCELLED_STATUS)
        self.assertEqual(r.status_code, 200)
        
        for booking in r.json['bookings']:
            self.assertEqual(booking['status']['status'], CANCELLED_STATUS)
        
    def checkDoneStatusBooking(self, _booking):
        booking = _booking.copy()
        
        booking['datetime_init'] = "2020-01-01 13:00:00"
        booking['worker_id'] = self.local.workers[0]['id']
        
        r = self.post_booking_admin(booking)
        id = dict(r.json)['booking']['id']
        self.assertEqual(r.status_code, 201)
        
        r = self.get_bookings_admin(date = "2020-01-01")
        self.assertEqual(r.status_code, 200)
        
        for booking in r.json['bookings']:
            if booking['id'] == id: self.assertEqual(booking['status']['status'], DONE_STATUS)
        
    def checkUpdateBookingAdmin(self, _booking):        
        #Cancelar todas las reservas
        r = self.get_bookings_admin(datetime_init = self.bookings[0]['datetime_init'], datetime_end = self.bookings[-1]['datetime_end'].replace('T', ' '), status = f"{PENDING_STATUS},{CONFIRMED_STATUS}")
        self.assertEqual(r.status_code, 200)
        
        for booking in r.json['bookings']:
            id = booking['id']
            booking['new_status'] = CANCELLED_STATUS
            booking['worker_id'] = booking['worker']['id']
            booking['services_ids'] = [self.local.services[0]['id']]
            booking.pop('worker')
            booking.pop('services')
            booking.pop('status')
            booking.pop('datetime_updated')
            booking.pop('datetime_end')
            booking.pop('datetime_created')
            booking.pop('id')
            booking.pop('comment')
            booking.pop('total_price')
            booking.pop('email_confirm')
            booking.pop('email_confirmed')
            booking.pop('email_cancelled')
            booking.pop('email_updated')
            r = self.update_booking_admin(id, booking)
            print("response:", r.json)
            self.assertEqual(r.status_code, 200)
            
            r = self.get_booking_admin(id)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(dict(r.json)['status']['status'], CANCELLED_STATUS)
        
        booking = _booking.copy()
        
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        session = dict(r.json)['session_token']
        id = dict(r.json)['booking']['id']
        
        r = self.get_booking_admin(id)
        self.assertEqual(r.status_code, 200)
        
        self.assertEqual(dict(r.json)['client_name'], booking['client_name'].strip().title())
        self.assertEqual(dict(r.json)['client_tlf'], booking['client_tlf'])
        
        booking['client_name'] = "Client Test 2"
        booking['new_status'] = CONFIRMED_STATUS
        r = self.update_booking_admin(id, booking)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(dict(r.json)['client_name'], booking['client_name'])
        
        booking['datetime_init'] = booking['datetime_init'].split(' ')[0] + ' ' + self.local.timetable[0]['closing_time']
        r = self.update_booking_admin(id, booking)
        self.assertEqual(r.status_code, 409)
        
        r = self.update_booking_admin(0, booking)
        self.assertEqual(r.status_code, 404)
        
        r = self.cancel_booking(session)
        self.assertEqual(r.status_code, 204)
        
        r = self.get_booking_admin(id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(dict(r.json)['status']['status'], CANCELLED_STATUS)
        
        booking['datetime_init'] = booking['datetime_init'].split(' ')[0] + ' ' + self.local.timetable[0]['opening_time']
        r = self.update_booking_admin(id, booking)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(dict(r.json)['status']['status'], booking['new_status'])
        
        r = self.cancel_booking(session)
        self.assertEqual(r.status_code, 204)
        
    def checkActionAdminsBooking(self, _booking):
        
        booking = _booking.copy()
        
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        id = dict(r.json)['booking']['id']
        session = dict(r.json)['session_token']
        worker_id = dict(r.json)['booking']['worker']['id']
        datetime_end = dict(r.json)['booking']['datetime_end'].replace('T', ' ')
        
        #Aumentar el tiempo de un servicio
        service_id = booking['services_ids'][0]
        r = self.client.get(getUrl('service', service_id))
        self.assertEqual(r.status_code, 200)
        service = dict(r.json)
        service.pop('id')
        service.pop('datetime_updated')
        service.pop('datetime_created')
        service['work_group'] = service['work_group']['id']
        service['duration'] += 20
        r = self.client.put(getUrl('service', service_id), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, data=json.dumps(service), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        
        r = self.get_booking_admin(id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(dict(r.json)['datetime_end'].replace('T', ' '), (datetime.datetime.strptime(datetime_end, "%Y-%m-%d %H:%M:%S") + datetime.timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S"))
        
        service['duration'] += 600
        r = self.client.put(getUrl('service', service_id), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, data=json.dumps(service), content_type='application/json')
        self.assertEqual(r.status_code, 409)

        #Cambiar el servicio a un work group que no incluya al trabajdor que tienen sus reservas
        service['work_group'] = self.local.work_groups[2]['id']
        r = self.client.put(getUrl('service', service_id), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, data=json.dumps(service), content_type='application/json')
        self.assertEqual(r.status_code, 409)
        
        #Borrar el trabajador
        
        r = self.client.delete(getUrl('worker', worker_id), headers={'Authorization': f"Bearer {self.local.access_token}"}, content_type='application/json')
        self.assertEqual(r.status_code, 409)
        
        #Cancelar reserva
        r = self.cancel_booking(session)
        self.assertEqual(r.status_code, 204)
        
        service['work_group'] = self.local.work_groups[2]['id']
        r = self.client.put(getUrl('service', service_id), headers={'Authorization': f"Bearer {self.local.refresh_token}"}, data=json.dumps(service), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        
        r = self.client.delete(getUrl('worker', worker_id), headers={'Authorization': f"Bearer {self.local.access_token}"}, content_type='application/json')
        self.assertEqual(r.status_code, 204)
        
        #Eliminar reserva
        booking = _booking.copy()
        booking['services_ids'] = [self.local.services[1]['id']]
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        id = dict(r.json)['booking']['id']
        session = dict(r.json)['session_token']
        
        r = self.delete_booking_admin(id)
        self.assertEqual(r.status_code, 204)
        
        r = self.get_booking_admin(id)
        self.assertEqual(r.status_code, 404)
        
        r = self.get_booking(session)
        self.assertEqual(r.status_code, 404)
        
        #Confirmar reserva con admin #TODO test
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 201)
        
        id = dict(r.json)['booking']['id']
        worker_id = dict(r.json)['booking']['worker']['id']
        
        # r = self.confirm_booking_admin(id)
        # self.assertEqual(r.status_code, 200)
        r = self.get_booking_admin(id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(dict(r.json)['status']['status'], CONFIRMED_STATUS)
        
        #Cancelar reserva con admin
        r = self.cancel_booking_admin(id)
        self.assertEqual(r.status_code, 204)
        r = self.get_booking_admin(id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(dict(r.json)['status']['status'], CANCELLED_STATUS)
        
        #Crear reserva "no disponible" con admin
        booking['datetime_init'] = "2020-01-01 00:00:00"
        r = self.post_booking(booking)
        self.assertEqual(r.status_code, 409)
        
        r = self.post_booking_local(booking)
        self.assertEqual(r.status_code, 409)
                
        booking['worker_id'] = worker_id
        r = self.post_booking_local(booking, force=True)
        print(r.json)
        self.assertEqual(r.status_code, 201)
        
    def test_integration_booking(self):
        
        self.configure_local()
        
        self.bookings = []
        
        time = (datetime.datetime.strptime(self.local.timetable[0]['opening_time'], "%H:%M:%S")).strftime("%H:%M:%S")
        data = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        booking = {
            "client_name": "  cliEnt teSt  ",
            "client_tlf": "123456789",
            "client_email": "client@example.com",
            "datetime_init": f"{data} {time}",
            "services_ids": [self.local.services[0]['id'], self.local.services[1]['id']]
        }
    
        #TEST 0: Falta de datos y datos incorrectos
        self.missingData(booking)

        #TEST 1: Fuera de horario
        self.outOfTimetable(booking)
    
        #TEST 2: Trabajador/es no disponible. Reservas ocupadas
        self.workerNotAvailable(booking)
        
        #TEST 3: Reserva correcta. Comprobacion de datos
        self.checkBooking(booking)
        
        #Test 4: Actualizar reserva
        self.checkUpdateBooking(booking)
        
        #Test 5: Lista de reservas
        self.checkListBooking(booking)
        
        #Test 6: Testear filtros por trabajador
        self.checkListFilterBooking()
        
        #Test 7: Testear filtros datos de cliente
        self.checkListFilterDataClientBooking()
        
        #Test 8: Testear filtros por estado
        self.checkListFilterStatusBooking()
        
        #Test 9: Testar cambios de estado a DONE
        self.checkDoneStatusBooking(booking)
        
        #Test 10: Testear actualizacion de reserva desde el local
        self.checkUpdateBookingAdmin(booking)
        
        #Test 11: Testear modificaciones administrativas
        self.checkActionAdminsBooking(booking)