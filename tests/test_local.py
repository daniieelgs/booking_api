# python -m unittest .\tests\test_local.py

import json
import unittest
from flask_testing import TestCase
from app import create_app, db
from globals import MIN_TIMEOUT_CONFIRM_BOOKING, TIMEOUT_CONFIRM_BOOKING
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
        return self.client.delete(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {token}"}, content_type='application/json')

    def get_local_api(self, token):
        return self.client.get(getUrl(ENDPOINT), headers={'Authorization': f"Bearer {token}"}, content_type='application/json')

    def print_all_locals(self):
        all_locals = self.client.get(getUrl('admin', 'local', 'all'),  headers={'Authorization': f"Bearer {self.admin_token}"}, content_type='application/json')
        
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
        
        data = {k:v for k,v in self.data.items()}
        local_settings = {k:v for k,v in self.local_settings.items()}
        smtp_settings = self.smtp_settings[:]
        
        data['local_settings'] = local_settings
        
        #Configuracion basica
        response_post = self.post_local(data)

        self.assertEqual(response_post.status_code, 201)

        self.local = dict(response_post.json)
        
        self.local['local']['local_settings'].pop('smtp_settings')
        
        self.assertEqual(self.local['local']['local_settings'], local_settings)

        self.assertEqual(len(self.local['warnings']), 1)

        r = self.del_local(self.local['access_token'])
        self.assertEqual(r.status_code, 204)

        #Test booking_tiemout
    
        #   1. Valor minimo
        data['local_settings']['booking_timeout'] = MIN_TIMEOUT_CONFIRM_BOOKING - 1
        response_post = self.post_local(data)

        self.assertEqual(response_post.status_code, 201)

        self.local = dict(response_post.json)
        
        self.assertEqual(self.local['local']['local_settings']['booking_timeout'], MIN_TIMEOUT_CONFIRM_BOOKING)
        
        self.assertEqual(len(self.local['warnings']), 2)
        
        r = self.del_local(self.local['access_token'])
        self.assertEqual(r.status_code, 204)
        
        #   2. Desactivado
        data['local_settings']['booking_timeout'] = -1
        response_post = self.post_local(data)
                
        self.assertEqual(response_post.status_code, 201)
        
        self.local = dict(response_post.json)
        
        self.assertEqual(self.local['local']['local_settings']['booking_timeout'], None)
        
        self.assertEqual(len(self.local['warnings']), 2)

        r = self.del_local(self.local['access_token'])
        self.assertEqual(r.status_code, 204)

        #   3. Valor por defecto
        
        data_copy = data.copy()
        data_copy['local_settings'].pop('booking_timeout')
        response_post = self.post_local(data)
                
        self.assertEqual(response_post.status_code, 201)
        
        self.local = dict(response_post.json)
        
        self.assertEqual(self.local['local']['local_settings']['booking_timeout'], TIMEOUT_CONFIRM_BOOKING)
        
        self.assertEqual(len(self.local['warnings']), 1)

        r = self.del_local(self.local['access_token'])
        self.assertEqual(r.status_code, 204)

        #SMTP Settings
        
        #Configuracion basica
        data['local_settings']['smtp_settings'] = smtp_settings

        response_post = self.post_local(data)
        
        self.assertEqual(response_post.status_code, 201)
        
        self.local = dict(response_post.json)
        
        smtp_settings = self.local['local']['local_settings']['smtp_settings']
        
        for i in range(len(smtp_settings)):
            smtp_settings[i].pop('reset_send_per_month')
            smtp_settings[i].pop('max_send_per_month')
        
        self.assertEqual(self.local['local']['local_settings']['smtp_settings'], smtp_settings)
        
        self.assertEqual(len(self.local['warnings']), 0)

        r = self.del_local(self.local['access_token'])
        self.assertEqual(r.status_code, 204)
        
        #Test conflictos

        #   1. Conflictos con nombres
        data['local_settings']['smtp_settings'][0]['name'] = data['local_settings']['smtp_settings'][1]['name']
        
        response_post = self.post_local(data)
                
        self.assertEqual(response_post.status_code, 409)
        
        data['local_settings']['smtp_settings'][0]['name'] = 'config-1'
        
        #   2. Conflictos con prioridades
        
        data['local_settings']['smtp_settings'][0]['priority'] = data['local_settings']['smtp_settings'][1]['priority']
        
        response_post = self.post_local(data)
                
        self.assertEqual(response_post.status_code, 409)
        
        data['local_settings']['smtp_settings'][0]['priority'] = 10
        
        #  3. Conflictos entre locales
        
            # Local 1
        response_post = self.post_local(data)
                
        self.assertEqual(response_post.status_code, 201)
        
        self.local = dict(response_post.json)
        
            # Local 2
        
        data['name'] = 'Local-Test-2'
        data['email'] = 'local_test_2@mail.com'
        
        response_post = self.post_local(data)
                
        self.assertEqual(response_post.status_code, 201)
        
        self.local2 = dict(response_post.json)

        self.local2['local']['local_settings']['smtp_settings'][0].pop('reset_send_per_month')
        self.local2['local']['local_settings']['smtp_settings'][0].pop('max_send_per_month')
        self.local2['local']['local_settings']['smtp_settings'][1].pop('reset_send_per_month')
        self.local2['local']['local_settings']['smtp_settings'][1].pop('max_send_per_month')
        
        self.assertEqual(self.local2['local']['local_settings']['smtp_settings'], data['local_settings']['smtp_settings'])

        self.assertEqual(len(self.local2['warnings']), 0)
        
            # Local 3
        
        data['name'] = 'Local-Test-3'
        data['email'] = 'local3@mail.com'
        
        data['local_settings']['smtp_settings'][0]['priority'] = 20
        
        response_post = self.post_local(data)
        
        self.assertEqual(response_post.status_code, 409)
        
        data['local_settings']['smtp_settings'][0]['priority'] = 10
        
        data['local_settings']['smtp_settings'][0]['name'] = 'config-2'
        
        response_post = self.post_local(data)
        
        self.assertEqual(response_post.status_code, 409)
        
        data['local_settings']['smtp_settings'][0]['name'] = 'config-1'
        
        response_post = self.post_local(data)
        
        self.assertEqual(response_post.status_code, 201)
        
        self.local3 = dict(response_post.json)
        
        r = self.del_local(self.local['access_token'])
        self.assertEqual(r.status_code, 204)
        
        r = self.del_local(self.local2['access_token'])
        self.assertEqual(r.status_code, 204)
        
        r = self.del_local(self.local3['access_token'])
        self.assertEqual(r.status_code, 204)

        #Warning por dominio:
        
        #   1. Cambiar el dominio del mail de un smtp
        data['local_settings']['smtp_settings'][0]['mail'] = 'info@local2.com'
        
        response_post = self.post_local(data)
        
        self.assertEqual(response_post.status_code, 201)
        
        self.local = dict(response_post.json)
        
        self.assertEqual(len(self.local['warnings']), 1)
        
        r = self.del_local(self.local['access_token'])
        self.assertEqual(r.status_code, 204)
        
        
        #   2. Dominio correcto
        data['local_settings']['smtp_settings'][0]['mail'] = 'info@local.com'
        
        response_post = self.post_local(data)
        
        self.assertEqual(response_post.status_code, 201)
        
        self.local = dict(response_post.json)
        
        self.assertEqual(len(self.local['warnings']), 0)
        
        r = self.del_local(self.local['access_token'])
        self.assertEqual(r.status_code, 204)
        
        #  3. Cambiar el dominio del local
        data['local_settings']['domain'] = 'local2.com'
        
        response_post = self.post_local(data)
        
        self.assertEqual(response_post.status_code, 201)
        
        self.local = dict(response_post.json)
                
        self.assertEqual(len(self.local['warnings']), len(data['local_settings']['smtp_settings']))
        
        r = self.del_local(self.local['access_token'])
        self.assertEqual(r.status_code, 204)
        
        data['local_settings']['domain'] = 'local.com'
        
        #No indicar tiempos de reseteo
        
        #   1. Sin reseteo de envios por dia
        reset_day = data['local_settings']['smtp_settings'][0].pop('reset_send_per_day')
        
        response_post = self.post_local(data)
                
        self.assertEqual(response_post.status_code, 400)
        
        data['local_settings']['smtp_settings'][0]['reset_send_per_day'] = reset_day
        
        #   2. Sin reseteo de envios por mes
        data['local_settings']['smtp_settings'][0]['max_send_per_month'] = 100
        
        response_post = self.post_local(data)
        
        self.assertEqual(response_post.status_code, 400)
        
        data['local_settings']['smtp_settings'][0]['reset_send_per_month'] = data['local_settings']['smtp_settings'][0]['reset_send_per_day']
        
        #Valores incorrectos
        #   1. Envios por dia negativos y mayores al maximo
        
        data['local_settings']['smtp_settings'][0]['send_per_day'] = -1
        
        response_post = self.post_local(data)
        
        self.assertEqual(response_post.status_code, 422)
        
        data['local_settings']['smtp_settings'][0]['send_per_day'] = smtp_settings[0]['max_send_per_day']
        
        #   2. Envios por mes negativos y mayores al maximo
        
        data['local_settings']['smtp_settings'][0]['send_per_month'] = -1
        
        response_post = self.post_local(data)
        
        self.assertEqual(response_post.status_code, 422)
        
        data['local_settings']['smtp_settings'][0]['send_per_month'] = 1
        
        
        response_post = self.post_local(data)
                
        self.assertEqual(response_post.status_code, 201)
        
        self.local = dict(response_post.json)
        
        r = self.del_local(self.local['access_token'])
        self.assertEqual(r.status_code, 204)
        
          
    def update_settings(self):
               
        data = {k:v for k,v in self.data.items()}
        local_settings = {k:v for k,v in self.local_settings.items()}
        smtp_settings = self.smtp_settings[:]
               
        for i in range(len(smtp_settings)):
            if 'reset_send_per_month' in smtp_settings[i]: smtp_settings[i].pop('reset_send_per_month')
            if 'max_send_per_month' in smtp_settings[i]: smtp_settings[i].pop('max_send_per_month')
            if 'send_per_month' in smtp_settings[i]: smtp_settings[i].pop('send_per_month')
               
        response_post = self.post_local(data)
        self.assertEqual(response_post.status_code, 201)
        self.local = dict(response_post.json)
        self.locals.append(self.local['local']['id'])

        #Configuracion basica
        local_settings['smtp_settings'] = smtp_settings
        data['local_settings'] = local_settings
        
        response_put = self.put_local(data, self.local['access_token'])
        self.assertEqual(response_put.status_code, 200)

        #Test conflictos
        
        #   1. Conflictos con nombres
        data['local_settings']['smtp_settings'][0]['name'] = data['local_settings']['smtp_settings'][1]['name']
        
        response_put = self.put_local(data, self.local['access_token'])
        
        self.assertEqual(response_put.status_code, 409)
        
        data['local_settings']['smtp_settings'][0]['name'] = 'config-1'
        
        #   2. Conflictos con prioridades
        
        data['local_settings']['smtp_settings'][0]['priority'] = data['local_settings']['smtp_settings'][1]['priority']
        
        response_put = self.put_local(data, self.local['access_token'])
        
        self.assertEqual(response_put.status_code, 409)
        
        data['local_settings']['smtp_settings'][0]['priority'] = 10
        
        #Añadir un nuevo smtp
        
        data['local_settings']['smtp_settings'].append(
            {
                "host": "smtp.sendgrid.net",
                "mail": "info@local.com",
                "max_send_per_day": 100,
                "name": "config-3",
                "password": "0000000000000000",
                "port": 587,
                "priority": 30,
                "reset_send_per_day": "2024-04-06T00:00:00",
                "send_per_day": 10,
                "user": "apikey"
            }
        )
        
        response_put = self.put_local(data, self.local['access_token'])
        
        self.assertEqual(response_put.status_code, 200)
                
        self.local_update = dict(response_put.json)
                
        smtp_settings = self.local_update['local']['local_settings']['smtp_settings']
        
        for i in range(len(smtp_settings)):
            if 'reset_send_per_month' in smtp_settings[i]: smtp_settings[i].pop('reset_send_per_month')
            if 'max_send_per_month' in smtp_settings[i]: smtp_settings[i].pop('max_send_per_month')
            if 'send_per_month' in smtp_settings[i]: smtp_settings[i].pop('send_per_month')
            
        self.assertEqual(self.local_update['local']['local_settings']['smtp_settings'], data['local_settings']['smtp_settings'])
        
        #Eliminar un smtp
        
        data['local_settings']['smtp_settings'] = smtp_settings[:-1]
        
        response_put = self.put_local(data, self.local['access_token'])
        
        self.assertEqual(response_put.status_code, 200)
                
        self.local_update = dict(response_put.json)
                
        smtp_settings = self.local_update['local']['local_settings']['smtp_settings']
        
        for i in range(len(smtp_settings)):
            if 'reset_send_per_month' in smtp_settings[i]: smtp_settings[i].pop('reset_send_per_month')
            if 'max_send_per_month' in smtp_settings[i]: smtp_settings[i].pop('max_send_per_month')
            if 'send_per_month' in smtp_settings[i]: smtp_settings[i].pop('send_per_month')
            
        self.assertEqual(self.local_update['local']['local_settings']['smtp_settings'], data['local_settings']['smtp_settings'])
        
        #Añadir valores month
        for i in range(len(data['local_settings']['smtp_settings'])):
            data['local_settings']['smtp_settings'][i]['send_per_month'] = 0
            data['local_settings']['smtp_settings'][i]['max_send_per_month'] = 100
            data['local_settings']['smtp_settings'][i]['reset_send_per_month'] = data['local_settings']['smtp_settings'][i]['reset_send_per_day']
            
        response_put = self.put_local(data, self.local['access_token'])
        
        self.assertEqual(response_put.status_code, 200)
        
        self.local_update = dict(response_put.json)
        
    def path_settings(self):
        
        smtp_settings = self.local_update['local']['local_settings']['smtp_settings']
        
        #Patch sin valores y sin warnings
        
        response_patch = self.patch_local({}, self.local['access_token'])
                
        self.assertEqual(response_patch.status_code, 200)
        
        self.local_patch = dict(response_patch.json)
        
        self.local_update['local'].pop('datetime_updated')
        self.local_patch['local'].pop('datetime_updated')
        
        self.assertEqual(self.local_patch, self.local_update)
        
        self.assertEqual(len(self.local_patch['warnings']), 0)
        
        #Patch con valores - Cambiar el dominio del local
        
        patch = {
            'local_settings': {
                'domain': 'local2.com'
            }
        }
        
        response_patch = self.patch_local(patch, self.local['access_token'])
        
        self.assertEqual(response_patch.status_code, 200)
        
        self.local_patch = dict(response_patch.json)
        
        self.assertEqual(self.local_patch['local']['local_settings']['domain'], 'local2.com')
        
        self.assertEqual(len(self.local_patch['warnings']), len(smtp_settings))
        
        #Patch sin valores y con warnings
        
        response_patch = self.patch_local({}, self.local['access_token'])
        
        self.assertEqual(response_patch.status_code, 200)
        
        self.local_patch = dict(response_patch.json)
        
        self.assertEqual(self.local_patch['local']['local_settings']['domain'], 'local2.com')
        
        self.assertEqual(len(self.local_patch['warnings']), len(smtp_settings))
        
        #Modificar smtp
        
        #Sin cambiar el smtp
        patch = {
            'local_settings': {
                'smtp_settings': [
                    {
                        'name': 'config-1'
                    }
                ]
            }
        }
        
        response_patch = self.patch_local(patch, self.local['access_token'])
                
        self.assertEqual(response_patch.status_code, 200)
        
        self.local_patch = dict(response_patch.json)
        
        self.assertEqual(self.local_patch['local']['local_settings']['smtp_settings'], smtp_settings)
        
        #Cambiar el nombre de un smtp
        
        patch = {
            'local_settings': {
                'smtp_settings': [
                    {
                        'name': 'config-1',
                        'new_name': 'config-1-modified',
                        'priority': 9
                    }
                ]
            }
        }
        
        response_patch = self.patch_local(patch, self.local['access_token'])
        
        self.assertEqual(response_patch.status_code, 200)
        
        self.local_patch = dict(response_patch.json)
        
        smtp_settings[0]['name'] = 'config-1-modified'
        smtp_settings[0]['priority'] = 9
        
        self.assertEqual(self.local_patch['local']['local_settings']['smtp_settings'], smtp_settings)
        
        #Modificar un valor de un smtp
        patch = {
            'local_settings': {
                'smtp_settings': [
                    {
                        'name': 'config-1-modified',
                        'send_per_day': 8
                    }
                ]
            }
        }
        
        response_patch = self.patch_local(patch, self.local['access_token'])
        
        self.assertEqual(response_patch.status_code, 200)
        
        self.local_patch = dict(response_patch.json)
        
        smtp_settings[0]['send_per_day'] = 8
        
        self.assertEqual(self.local_patch['local']['local_settings']['smtp_settings'], smtp_settings)
        
        #Crear conflicto
        
        # 1. Cambiar el nombre de un smtp a uno que ya existe
        
        patch = {
            'local_settings': {
                'smtp_settings': [
                    {
                        'name': 'config-1-modified',
                        'new_name': 'config-2'
                    }
                ]
            }
        }
        
        response_patch = self.patch_local(patch, self.local['access_token'])
        
        self.assertEqual(response_patch.status_code, 409)
        
        # 2. Cambiar la prioridad de un smtp a una que ya existe
        
        patch = {
            'local_settings': {
                'smtp_settings': [
                    {
                        'name': 'config-1-modified',
                        'priority': 20
                    }
                ]
            }
        }
        
        self.assertEqual(response_patch.status_code, 409)
        
        #Crear un nuevo smtp
        # 1. Datos faltantes
        patch = { #Falta el password
            'local_settings': {
                'smtp_settings': [
                    {
                        'name': 'config-3',
                        "host": "smtp-relay.brevo.com",
                        "mail": "info@local.com",
                        "max_send_per_day": 300,
                        "port": 587,
                        "priority": 30,
                        "reset_send_per_day": "2024-03-10T00:00:00",
                        "send_per_day": 100,
                        "send_per_month": 0,
                        "user": "user@mail.com"
                    }
                ]
            }
        }
        
        response_patch = self.patch_local(patch, self.local['access_token'])
        
        self.assertEqual(response_patch.status_code, 404)
        
        error_message = f"The smtp setting '{patch['local_settings']['smtp_settings'][0]['name']}' does not exist. The field 'password' is required."
        
        self.assertEqual(response_patch.json['message'], error_message)
        
        # 2. Datos correctos
        
        patch['local_settings']['smtp_settings'][0]['password'] = '0000000000000000'
        
        response_patch = self.patch_local(patch, self.local['access_token'])
        
        self.assertEqual(response_patch.status_code, 200)
        
        self.local_patch = dict(response_patch.json)
        
        self.assertEqual(len(self.local_patch['local']['local_settings']['smtp_settings']), len(smtp_settings) + 1)
        
        #Eliminar un smtp
        
        patch = {
            'local_settings': {
                'smtp_settings': [
                    {
                        'name': 'config-3',
                        'remove': True
                    }
                ]
            }
        }
                
        response_patch = self.patch_local(patch, self.local['access_token'])
        
        self.assertEqual(response_patch.status_code, 200)  
        
        self.local_patch = dict(response_patch.json)
        
        self.assertEqual(len(self.local_patch['local']['local_settings']['smtp_settings']), len(smtp_settings))
        

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
            "confirmation_link": "https://www.local.com/confirm/{booking_token}",
            "cancel_link": "https://www.local.com/cancel/{booking_token}",
            "update_link": "https://www.local.com/cancel/{booking_token}",
            "booking_timeout": 10
        }
        
        self.smtp_settings = [
            {
                "host": "smtp-relay.brevo.com",
                "mail": "info@local.com",
                "max_send_per_day": 300,
                "name": "config-1",
                "password": "0000000000000000000",
                "port": 587,
                "priority": 10,
                "reset_send_per_day": "2024-03-10T00:00:00",
                "send_per_day": 100,
                "send_per_month": 0,
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
                "reset_send_per_day": "2024-04-06T00:00:00",
                "send_per_day": 10,
                "send_per_month": 0,
                "user": "apikey"
            },
        ]
        
        self.create_settings()
        self.update_settings()
        self.path_settings()

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
