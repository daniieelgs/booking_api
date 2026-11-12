"""helpers/ReportController.py: the fallback-report file store (real files in a temp dir)."""
import glob
import json
import os
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

from helpers import ReportController as reports


class ReportsTestCase(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = os.path.join(tmp.name, 'reports')
        self.file = os.path.join(self.folder, 'fallback.json')
        patcher = mock.patch.dict(os.environ, {'REPORTS_FILE': self.file, 'MAX_REPORTS_FILE_SIZE': str(10_000_000)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def stored(self, path=None):
        with open(path or self.file, encoding='utf-8') as f:
            return json.load(f)


def request(headers=None, remote_addr='10.0.0.1'):
    return SimpleNamespace(headers=headers or {}, remote_addr=remote_addr)


class TestConfigGetters(ReportsTestCase):

    def test_reads_the_environment_on_every_call(self):
        self.assertEqual(reports.getReportsFile(), self.file)
        with mock.patch.dict(os.environ, {'REPORTS_FILE': 'other.json'}):
            self.assertEqual(reports.getReportsFile(), 'other.json')

    def test_sizes_are_integers(self):
        with mock.patch.dict(os.environ, {'MAX_REPORT_SIZE': '123', 'MAX_REPORTS_FILE_SIZE': '456'}):
            self.assertEqual(reports.getMaxReportSize(), 123)
            self.assertEqual(reports.getMaxReportsFileSize(), 456)

    def test_lock_file_sits_next_to_the_reports_file(self):
        self.assertEqual(reports.getLockFile(), self.file + '.lock')


class TestBuildRequestMeta(unittest.TestCase):

    def test_uses_the_remote_address_by_default(self):
        self.assertEqual(reports.buildRequestMeta(request())['ip'], '10.0.0.1')

    def test_prefers_the_first_forwarded_address(self):
        meta = reports.buildRequestMeta(request({'X-Forwarded-For': '1.2.3.4, 10.0.0.9'}))

        self.assertEqual(meta['ip'], '1.2.3.4')

    def test_collects_the_interesting_headers(self):
        meta = reports.buildRequestMeta(request({'User-Agent': 'UA', 'Origin': 'https://a.com', 'Referer': 'https://a.com/x',
                                                 'Accept-Language': 'es', 'Authorization': 'Bearer secret'}))

        self.assertEqual(meta['headers'], {'user_agent': 'UA', 'origin': 'https://a.com', 'referer': 'https://a.com/x',
                                           'accept_language': 'es'})

    def test_never_stores_credentials(self):
        meta = reports.buildRequestMeta(request({'Authorization': 'Bearer secret', 'Cookie': 'session=abc'}))

        self.assertNotIn('secret', json.dumps(meta))
        self.assertNotIn('session=abc', json.dumps(meta))

    def test_missing_headers_are_none(self):
        self.assertEqual(reports.buildRequestMeta(request())['headers']['user_agent'], None)


class TestSaveReport(ReportsTestCase):

    def test_creates_the_folder_and_the_file(self):
        reports.saveReport({'error': 'boom'}, {'ip': '1.1.1.1'})

        self.assertEqual(len(self.stored()), 1)

    def test_returns_the_id_and_datetime_of_the_stored_entry(self):
        report_id, report_datetime = reports.saveReport({'a': 1}, {})

        entry = self.stored()[0]
        self.assertEqual(entry['id'], report_id)
        self.assertEqual(entry['datetime'], report_datetime.isoformat())

    def test_entry_contains_meta_report_and_server(self):
        reports.saveReport({'booking': {'x': 1}}, {'ip': '1.1.1.1', 'headers': {'user_agent': 'UA'}})

        entry = self.stored()[0]
        self.assertEqual(entry['ip'], '1.1.1.1')
        self.assertEqual(entry['report'], {'booking': {'x': 1}})
        self.assertTrue(entry['server'])

    def test_reports_are_appended_in_order(self):
        reports.saveReport({'n': 1}, {})
        reports.saveReport({'n': 2}, {})
        reports.saveReport({'n': 3}, {})

        self.assertEqual([e['report']['n'] for e in self.stored()], [1, 2, 3])

    def test_ids_are_unique(self):
        ids = {reports.saveReport({}, {})[0] for _ in range(20)}

        self.assertEqual(len(ids), 20)

    def test_accepts_arbitrary_json_including_unicode(self):
        reports.saveReport({'mensaje': 'reserva fallida ñ €', 'lista': [1, {'a': None}]}, {})

        self.assertEqual(self.stored()[0]['report']['mensaje'], 'reserva fallida ñ €')

    def test_non_serializable_values_are_stringified_instead_of_failing(self):
        reports.saveReport({'when': __import__('datetime').datetime(2030, 1, 1)}, {})

        self.assertIn('2030-01-01', self.stored()[0]['report']['when'])

    def test_no_temporary_file_is_left_behind(self):
        reports.saveReport({}, {})

        self.assertEqual(sorted(os.listdir(self.folder)), ['fallback.json', 'fallback.json.lock'])

    def test_concurrent_writers_lose_nothing(self):
        errors = []

        def write(n):
            try:
                reports.saveReport({'n': n}, {})
            except Exception as e:  # pragma: no cover - reported below
                errors.append(e)

        threads = [threading.Thread(target=write, args=(n,)) for n in range(25)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(sorted(e['report']['n'] for e in self.stored()), list(range(25)))


class TestCorruptFile(ReportsTestCase):

    def write_raw(self, text):
        os.makedirs(self.folder, exist_ok=True)
        with open(self.file, 'w', encoding='utf-8') as f:
            f.write(text)

    def test_invalid_json_is_set_aside_and_a_fresh_file_started(self):
        self.write_raw('{not json')

        reports.saveReport({'n': 1}, {})

        self.assertEqual(len(self.stored()), 1)
        corrupt = glob.glob(self.file + '.corrupt.*')
        self.assertEqual(len(corrupt), 1)
        with open(corrupt[0], encoding='utf-8') as f:
            self.assertEqual(f.read(), '{not json')

    def test_a_json_object_instead_of_a_list_is_treated_as_corrupt(self):
        self.write_raw('{"a": 1}')

        reports.saveReport({'n': 1}, {})

        self.assertEqual(len(self.stored()), 1)
        self.assertEqual(len(glob.glob(self.file + '.corrupt.*')), 1)

    def test_empty_file_is_treated_as_corrupt_and_does_not_block_new_reports(self):
        self.write_raw('')

        reports.saveReport({'n': 1}, {})

        self.assertEqual(len(self.stored()), 1)

    def test_valid_file_is_extended_not_replaced(self):
        self.write_raw('[{"id": "old"}]')

        reports.saveReport({'n': 1}, {})

        self.assertEqual([e['id'] for e in self.stored()][0], 'old')
        self.assertEqual(len(self.stored()), 2)


class TestRotation(ReportsTestCase):

    def test_a_full_file_is_rotated_and_a_new_one_started(self):
        reports.saveReport({'n': 1}, {})
        with mock.patch.dict(os.environ, {'MAX_REPORTS_FILE_SIZE': '10'}):
            reports.saveReport({'n': 2}, {})

        rotated = [p for p in glob.glob(os.path.join(self.folder, 'fallback.*.json'))]
        self.assertEqual(len(rotated), 1)
        self.assertEqual([e['report']['n'] for e in self.stored(rotated[0])], [1])
        self.assertEqual([e['report']['n'] for e in self.stored()], [2])

    def test_a_small_file_is_not_rotated(self):
        reports.saveReport({'n': 1}, {})
        reports.saveReport({'n': 2}, {})

        self.assertEqual(glob.glob(os.path.join(self.folder, 'fallback.*.json')), [])
        self.assertEqual(len(self.stored()), 2)


if __name__ == '__main__':
    unittest.main()
