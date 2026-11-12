import io
import json
import os
import unittest

from flask_testing import TestCase

from app import create_app, db
from globals import IMAGE_TYPE_GALLERY, IMAGE_TYPE_LOGOS, PARAM_FILE_NAME
from tests.config_test import config_test, getUrl
from tests.configure_local_base import LocalBase

PNG = b'\x89PNG\r\n\x1a\n-fake-image-bytes'


class TestFiles(TestCase):

    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):
        db.create_all()
        config_test.config(db=db)
        self.admin_token = config_test.ADMIN_TOKEN
        base = LocalBase(self.client, self.admin_token, self.assertEqual)
        base.create_local(-1, set_local_settings=False, set_smtp_settings=False)
        self.locals.extend(base.locals)
        self.local = base
        self.local_id = base.local['id']

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)

    def bearer(self, token=None):
        return {'Authorization': f'Bearer {token or self.local.refresh_token}'}

    def upload(self, kind, filename='image.png', content=PNG, token=None, auth=True, field=PARAM_FILE_NAME):
        data = {field: (io.BytesIO(content), filename)}
        return self.client.post(getUrl('files', kind), data=data, headers=self.bearer(token) if auth else {},
                                content_type='multipart/form-data')

    def delete(self, kind, name, token=None, auth=True):
        return self.client.delete(getUrl('files', kind, name), headers=self.bearer(token) if auth else {})

    def listing(self, kind, local_id=None):
        return self.client.get(getUrl('files', 'local', local_id or self.local_id, kind))

    def public_url(self, kind, name):
        return f"/{os.environ['PUBLIC_FOLDER_URL']}/images/local/{self.local_id}/{kind}/{name}"

    def disk_path(self, *parts):
        return os.path.join(os.getcwd(), os.environ['PUBLIC_FOLDER'], self.local_id, *parts)

    def create_other_local(self):
        data = {
            'name': 'Other-Local', 'tlf': '987654321', 'email': 'other@test.com', 'address': 'Other Address',
            'postal_code': '11111', 'village': 'Other Village', 'province': 'Other Province', 'location': 'Europe/Madrid',
        }
        r = self.client.post(getUrl('local'), data=json.dumps(data), headers=self.bearer(self.admin_token), content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.locals.append(r.json['local']['id'])
        return r.json

    # --- logos ---

    def test_upload_logo_returns_public_url(self):
        r = self.upload('logos', 'logo.png')

        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json['url'], self.public_url(IMAGE_TYPE_LOGOS, 'logo.png'))

    def test_upload_logo_is_stored_on_disk(self):
        self.upload('logos', 'logo.png')

        with open(self.disk_path('images', IMAGE_TYPE_LOGOS, 'logo.png'), 'rb') as f:
            self.assertEqual(f.read(), PNG)

    def test_upload_logo_is_listed(self):
        self.upload('logos', 'logo.png')

        r = self.listing('logos')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json, [{'url': self.public_url(IMAGE_TYPE_LOGOS, 'logo.png')}])

    def test_upload_logo_duplicate_is_409(self):
        self.upload('logos', 'logo.png')

        r = self.upload('logos', 'logo.png')

        self.assertEqual(r.status_code, 409)

    def test_upload_logo_filename_is_sanitized(self):
        r = self.upload('logos', '../../evil name.png')

        self.assertEqual(r.status_code, 201)
        self.assertNotIn('..', r.json['url'])
        self.assertTrue(r.json['url'].endswith('/evil_name.png'))

    def test_upload_logo_invalid_extension_is_400(self):
        r = self.upload('logos', 'script.exe')

        self.assertEqual(r.status_code, 400)

    def test_upload_logo_without_extension_is_400(self):
        r = self.upload('logos', 'logo')

        self.assertEqual(r.status_code, 400)

    def test_upload_logo_missing_file_field_is_400(self):
        r = self.upload('logos', field='not-the-expected-field')

        self.assertEqual(r.status_code, 400)

    def test_upload_logo_empty_filename_is_400(self):
        r = self.upload('logos', filename='')

        self.assertEqual(r.status_code, 400)

    def test_upload_logo_requires_authentication(self):
        r = self.upload('logos', auth=False)

        self.assertEqual(r.status_code, 401)

    def test_delete_logo(self):
        self.upload('logos', 'logo.png')

        r = self.delete('logos', 'logo.png')

        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.listing('logos').json, [])
        self.assertFalse(os.path.exists(self.disk_path('images', IMAGE_TYPE_LOGOS, 'logo.png')))

    def test_delete_logo_twice_is_404(self):
        self.upload('logos', 'logo.png')
        self.delete('logos', 'logo.png')

        r = self.delete('logos', 'logo.png')

        self.assertEqual(r.status_code, 404)

    def test_delete_unknown_logo_is_404(self):
        r = self.delete('logos', 'nope.png')

        self.assertEqual(r.status_code, 404)

    def test_delete_logo_requires_authentication(self):
        self.upload('logos', 'logo.png')

        r = self.delete('logos', 'logo.png', auth=False)

        self.assertEqual(r.status_code, 401)

    def test_delete_logo_of_another_local_is_404(self):
        self.upload('logos', 'logo.png')
        other = self.create_other_local()

        r = self.delete('logos', 'logo.png', token=other['refresh_token'])

        self.assertEqual(r.status_code, 404)
        self.assertEqual(len(self.listing('logos').json), 1)

    # --- gallery ---

    def test_upload_gallery_image_returns_public_url(self):
        r = self.upload('gallery', 'photo.jpg')

        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json['url'], self.public_url(IMAGE_TYPE_GALLERY, 'photo.jpg'))

    def test_gallery_and_logos_are_listed_separately(self):
        self.upload('logos', 'logo.png')
        self.upload('gallery', 'photo.jpg')

        self.assertEqual(self.listing('logos').json, [{'url': self.public_url(IMAGE_TYPE_LOGOS, 'logo.png')}])
        self.assertEqual(self.listing('gallery').json, [{'url': self.public_url(IMAGE_TYPE_GALLERY, 'photo.jpg')}])

    def test_same_filename_can_exist_as_logo_and_gallery_image(self):
        self.assertEqual(self.upload('logos', 'same.png').status_code, 201)
        self.assertEqual(self.upload('gallery', 'same.png').status_code, 201)

    def test_upload_gallery_duplicate_is_409(self):
        self.upload('gallery', 'photo.jpg')

        r = self.upload('gallery', 'photo.jpg')

        self.assertEqual(r.status_code, 409)

    def test_upload_gallery_invalid_extension_is_400(self):
        r = self.upload('gallery', 'photo.gif')

        self.assertEqual(r.status_code, 400)

    def test_upload_gallery_requires_authentication(self):
        r = self.upload('gallery', auth=False)

        self.assertEqual(r.status_code, 401)

    def test_list_gallery_is_public_and_empty_by_default(self):
        r = self.listing('gallery')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json, [])

    def test_list_only_returns_files_of_the_requested_local(self):
        self.upload('gallery', 'photo.jpg')
        other = self.create_other_local()

        r = self.listing('gallery', local_id=other['local']['id'])

        self.assertEqual(r.json, [])

    def test_delete_unknown_gallery_image_is_404(self):
        r = self.delete('gallery', 'nope.jpg')

        self.assertEqual(r.status_code, 404)

    def test_delete_gallery_requires_authentication(self):
        r = self.delete('gallery', 'photo.jpg', auth=False)

        self.assertEqual(r.status_code, 401)

    # DELETE gallery/<name> calls deleteImage(name, IMAGE_TYPE_LOGOS), so gallery images can never be deleted.
    def test_delete_gallery_image(self):
        self.upload('gallery', 'photo.jpg')

        r = self.delete('gallery', 'photo.jpg')

        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.listing('gallery').json, [])

    # --- pages ---

    def test_upload_page_stores_it_on_disk(self):
        r = self.upload('pages', 'email_confirmed.html', b'<html><title>Hi</title></html>')

        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json['url'], f"/{os.environ['PUBLIC_FOLDER_URL']}/pages/local/{self.local_id}/email_confirmed.html")
        with open(self.disk_path('pages', 'email_confirmed.html'), 'rb') as f:
            self.assertEqual(f.read(), b'<html><title>Hi</title></html>')

    def test_upload_page_again_overwrites_it(self):
        self.upload('pages', 'email_confirmed.html', b'<html>v1</html>')

        r = self.upload('pages', 'email_confirmed.html', b'<html>v2</html>')

        self.assertEqual(r.status_code, 201)
        with open(self.disk_path('pages', 'email_confirmed.html'), 'rb') as f:
            self.assertEqual(f.read(), b'<html>v2</html>')

    def test_upload_page_invalid_extension_is_400(self):
        r = self.upload('pages', 'page.exe')

        self.assertEqual(r.status_code, 400)

    def test_upload_page_requires_authentication(self):
        r = self.upload('pages', 'page.html', auth=False)

        self.assertEqual(r.status_code, 401)

    def test_delete_page(self):
        self.upload('pages', 'page.html', b'<html></html>')

        r = self.delete('pages', 'page.html')

        self.assertEqual(r.status_code, 204)
        self.assertFalse(os.path.exists(self.disk_path('pages', 'page.html')))

    def test_delete_unknown_page_is_404(self):
        r = self.delete('pages', 'nope.html')

        self.assertEqual(r.status_code, 404)

    def test_delete_page_requires_authentication(self):
        self.upload('pages', 'page.html', b'<html></html>')

        r = self.delete('pages', 'page.html', auth=False)

        self.assertEqual(r.status_code, 401)

    def test_delete_page_of_another_local_is_404(self):
        self.upload('pages', 'page.html', b'<html></html>')
        other = self.create_other_local()

        r = self.delete('pages', 'page.html', token=other['refresh_token'])

        self.assertEqual(r.status_code, 404)
        self.assertTrue(os.path.exists(self.disk_path('pages', 'page.html')))
