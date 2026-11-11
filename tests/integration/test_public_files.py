import io
import json
import os

from flask_testing import TestCase

from app import create_app, db
from globals import IMAGE_TYPE_GALLERY, IMAGE_TYPE_LOGOS, PARAM_FILE_NAME
from tests.config_test import config_test, getUrl
from tests.configure_local_base import LocalBase

PNG = b'\x89PNG\r\n\x1a\n-fake-image-bytes'
JPG = b'\xff\xd8\xff-fake-jpeg-bytes'
HTML = b'<html><head><title>Subject</title></head><body>Hello</body></html>'


class TestPublicFiles(TestCase):

    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):
        db.create_all()
        config_test.config(db=db)
        base = LocalBase(self.client, config_test.ADMIN_TOKEN, self.assertEqual)
        base.create_local(-1, set_local_settings=False, set_smtp_settings=False)
        self.locals.extend(base.locals)
        self.local = base
        self.local_id = base.local['id']

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)

    def upload(self, kind, filename, content, mimetype=None):
        stream = (io.BytesIO(content), filename, mimetype) if mimetype else (io.BytesIO(content), filename)
        r = self.client.post(getUrl('files', kind), data={PARAM_FILE_NAME: stream},
                             headers={'Authorization': f'Bearer {self.local.refresh_token}'}, content_type='multipart/form-data')
        self.assertEqual(r.status_code, 201)
        return r.json['url']

    def base(self):
        return f"/{os.environ['PUBLIC_FOLDER_URL']}"

    def logo_url(self, name, local_id=None):
        return f"{self.base()}/images/local/{local_id or self.local_id}/{IMAGE_TYPE_LOGOS}/{name}"

    def gallery_url(self, name, local_id=None):
        return f"{self.base()}/images/local/{local_id or self.local_id}/{IMAGE_TYPE_GALLERY}/{name}"

    def page_url(self, name, local_id=None):
        return f"{self.base()}/pages/local/{local_id or self.local_id}/{name}"

    def disk_path(self, *parts):
        return os.path.join(os.getcwd(), os.environ['PUBLIC_FOLDER'], self.local_id, *parts)

    # --- logos ---

    def test_logo_is_served_with_its_bytes_and_mimetype(self):
        url = self.upload('logos', 'logo.png', PNG, 'image/png')

        r = self.client.get(url)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, PNG)
        self.assertEqual(r.headers['Content-Type'], 'image/png')

    def test_logo_is_served_inline_with_its_filename(self):
        self.upload('logos', 'logo.png', PNG, 'image/png')

        r = self.client.get(self.logo_url('logo.png'))

        self.assertEqual(r.headers['Content-Disposition'], 'inline; filename="logo.png"')

    def test_logo_does_not_require_authentication(self):
        self.upload('logos', 'logo.png', PNG, 'image/png')

        r = self.client.get(self.logo_url('logo.png'), headers={})

        self.assertNotEqual(r.status_code, 401)
        self.assertEqual(r.status_code, 200)

    def test_unknown_logo_is_404(self):
        r = self.client.get(self.logo_url('nope.png'))

        self.assertEqual(r.status_code, 404)

    def test_logo_of_unknown_local_is_404(self):
        self.upload('logos', 'logo.png', PNG, 'image/png')

        r = self.client.get(self.logo_url('logo.png', local_id='does-not-exist'))

        self.assertEqual(r.status_code, 404)

    def test_gallery_image_is_not_served_as_logo(self):
        self.upload('gallery', 'photo.jpg', JPG, 'image/jpeg')

        r = self.client.get(self.logo_url('photo.jpg'))

        self.assertEqual(r.status_code, 404)

    def test_deleted_logo_is_404(self):
        self.upload('logos', 'logo.png', PNG, 'image/png')
        self.client.delete(getUrl('files', 'logos', 'logo.png'), headers={'Authorization': f'Bearer {self.local.refresh_token}'})

        r = self.client.get(self.logo_url('logo.png'))

        self.assertEqual(r.status_code, 404)

    def test_logo_registered_but_missing_on_disk_is_404(self):
        self.upload('logos', 'logo.png', PNG, 'image/png')
        os.remove(self.disk_path('images', IMAGE_TYPE_LOGOS, 'logo.png'))

        r = self.client.get(self.logo_url('logo.png'))

        self.assertEqual(r.status_code, 404)

    # --- gallery ---

    def test_gallery_image_is_served_with_its_bytes_and_mimetype(self):
        url = self.upload('gallery', 'photo.jpg', JPG, 'image/jpeg')

        r = self.client.get(url)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, JPG)
        self.assertEqual(r.headers['Content-Type'], 'image/jpeg')

    def test_unknown_gallery_image_is_404(self):
        r = self.client.get(self.gallery_url('nope.jpg'))

        self.assertEqual(r.status_code, 404)

    def test_logo_is_not_served_as_gallery_image(self):
        self.upload('logos', 'logo.png', PNG, 'image/png')

        r = self.client.get(self.gallery_url('logo.png'))

        self.assertEqual(r.status_code, 404)

    # --- pages ---

    def test_page_is_served_as_html(self):
        url = self.upload('pages', 'email_confirmed.html', HTML)

        r = self.client.get(url)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, HTML)
        self.assertTrue(r.headers['Content-Type'].startswith('text/html'))

    def test_page_does_not_require_authentication(self):
        self.upload('pages', 'email_confirmed.html', HTML)

        r = self.client.get(self.page_url('email_confirmed.html'))

        self.assertEqual(r.status_code, 200)

    def test_updated_page_serves_the_new_content(self):
        self.upload('pages', 'email_confirmed.html', b'<html>v1</html>')
        self.upload('pages', 'email_confirmed.html', b'<html>v2</html>')

        r = self.client.get(self.page_url('email_confirmed.html'))

        self.assertEqual(r.data, b'<html>v2</html>')

    def test_unknown_page_is_404(self):
        r = self.client.get(self.page_url('nope.html'))

        self.assertEqual(r.status_code, 404)

    def test_page_of_unknown_local_is_404(self):
        self.upload('pages', 'email_confirmed.html', HTML)

        r = self.client.get(self.page_url('email_confirmed.html', local_id='does-not-exist'))

        self.assertEqual(r.status_code, 404)

    def test_page_is_scoped_to_its_local(self):
        self.upload('pages', 'email_confirmed.html', HTML)
        other = self.client.post(getUrl('local'), data=json.dumps({
            'name': 'Other-Local', 'tlf': '987654321', 'email': 'other@test.com', 'address': 'Other Address',
            'postal_code': '11111', 'village': 'Other Village', 'province': 'Other Province', 'location': 'Europe/Madrid',
        }), headers={'Authorization': f'Bearer {config_test.ADMIN_TOKEN}'}, content_type='application/json')
        self.assertEqual(other.status_code, 201)
        self.locals.append(other.json['local']['id'])

        r = self.client.get(self.page_url('email_confirmed.html', local_id=other.json['local']['id']))

        self.assertEqual(r.status_code, 404)

    def test_deleted_page_is_404(self):
        self.upload('pages', 'email_confirmed.html', HTML)
        self.client.delete(getUrl('files', 'pages', 'email_confirmed.html'), headers={'Authorization': f'Bearer {self.local.refresh_token}'})

        r = self.client.get(self.page_url('email_confirmed.html'))

        self.assertEqual(r.status_code, 404)
