import json
import os
import shutil

from flask_testing import TestCase

from app import create_app, db
from tests import config_test, getUrl

ENDPOINT = 'report/fallback'

TEST_REPORTS_FOLDER = os.path.join('tests', 'private_reports')
TEST_REPORTS_FILE = os.path.join(TEST_REPORTS_FOLDER, 'fallback_reports.json')


class TestReport(TestCase):
    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):

        db.create_all()
        config_test.config(db=db)
        self.admin_token = config_test.ADMIN_TOKEN

        os.environ['REPORTS_FILE'] = TEST_REPORTS_FILE

    def tearDown(self):

        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)

        os.environ.pop('REPORTS_FILE', None)

        if os.path.exists(TEST_REPORTS_FOLDER):
            shutil.rmtree(TEST_REPORTS_FOLDER)

    def readReports(self):
        with open(TEST_REPORTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_post_report_creates_file(self):

        report = {
            "browser": "Chrome",
            "browserVersion": "126.0",
            "os": "Windows 11",
            "device": "desktop",
            "primaryError": {"status": 0, "message": "Failed to fetch"},
            "url": "https://example.com/booking"
        }

        response = self.client.post(getUrl(ENDPOINT), data=json.dumps(report), content_type='application/json')

        self.assertEqual(response.status_code, 201)
        self.assertIn('id', response.json)
        self.assertIn('datetime', response.json)

        reports = self.readReports()
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]['report'], report)
        self.assertEqual(reports[0]['id'], response.json['id'])
        self.assertIn('server', reports[0])
        self.assertIn('headers', reports[0])

    def test_post_report_appends(self):

        report1 = {"browser": "Chrome"}
        report2 = {"browser": "Firefox"}

        self.client.post(getUrl(ENDPOINT), data=json.dumps(report1), content_type='application/json')
        self.client.post(getUrl(ENDPOINT), data=json.dumps(report2), content_type='application/json')

        reports = self.readReports()
        self.assertEqual(len(reports), 2)
        self.assertEqual(reports[0]['report'], report1)
        self.assertEqual(reports[1]['report'], report2)

    def test_post_report_does_not_require_authentication(self):

        report = {"browser": "Safari"}

        response = self.client.post(getUrl(ENDPOINT), data=json.dumps(report), content_type='application/json')

        self.assertEqual(response.status_code, 201)

    def test_post_report_accepts_array(self):

        report = [{"browser": "Chrome"}, {"browser": "Edge"}]

        response = self.client.post(getUrl(ENDPOINT), data=json.dumps(report), content_type='application/json')

        self.assertEqual(response.status_code, 201)

        reports = self.readReports()
        self.assertEqual(reports[0]['report'], report)

    def test_post_report_empty_body_returns_400(self):

        response = self.client.post(getUrl(ENDPOINT), data='', content_type='application/json')

        self.assertEqual(response.status_code, 400)

    def test_post_report_invalid_json_returns_400(self):

        response = self.client.post(getUrl(ENDPOINT), data='this is not json', content_type='text/plain')

        self.assertEqual(response.status_code, 400)

    def test_post_report_too_large_returns_413(self):

        big_report = {"payload": "x" * (1024 * 1024)} # 1MB, mayor que MAX_REPORT_SIZE de test

        os.environ['MAX_REPORT_SIZE'] = str(1024 * 10) # 10KB

        try:
            response = self.client.post(getUrl(ENDPOINT), data=json.dumps(big_report), content_type='application/json')
            self.assertEqual(response.status_code, 413)
        finally:
            os.environ.pop('MAX_REPORT_SIZE', None)

    def test_reports_file_rotates_when_too_big(self):

        os.environ['MAX_REPORTS_FILE_SIZE'] = '10' # cualquier reporte ya lo supera

        try:
            self.client.post(getUrl(ENDPOINT), data=json.dumps({"browser": "Chrome"}), content_type='application/json')
            self.client.post(getUrl(ENDPOINT), data=json.dumps({"browser": "Firefox"}), content_type='application/json')

            rotated = [f for f in os.listdir(TEST_REPORTS_FOLDER) if f != 'fallback_reports.json' and f != 'fallback_reports.json.lock']
            self.assertTrue(len(rotated) >= 1)

            # El fichero actual solo contiene el último reporte, no los rotados
            reports = self.readReports()
            self.assertEqual(len(reports), 1)
        finally:
            os.environ.pop('MAX_REPORTS_FILE_SIZE', None)
