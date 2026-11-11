import smtplib
from unittest import mock

from flask_testing import TestCase

from app import create_app, db
from helpers import EmailController
from helpers.EmailController import mail_local_sender, send_mail
from models.local import LocalModel
from models.smtp_settings import SmtpSettingsModel
from tests.config_test import config_test
from tests.configure_local_base import configure


def send_args():
    return dict(to='client@example.com', subject='Subject', content='<p>Hello</p>', type='html', name='Local')


class SmtpFallbackTestCase(TestCase):
    set_smtp_settings = True

    def create_app(self):
        app = create_app(config_test)
        self.locals = []
        return app

    def setUp(self):
        db.create_all()
        config_test.config(db=db)
        self.local = configure(self.client, config_test.ADMIN_TOKEN, self.assertEqual, -1,
                               set_smtp_settings=self.set_smtp_settings, set_timetable=False,
                               set_work_groups=False, set_services=False, set_workers=False)
        self.locals = self.local.locals

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        config_test.drop(self.locals)

    def local_settings(self):
        return LocalModel.query.get(self.local.local['id']).local_settings

    def counters(self, priority):
        db.session.expire_all()
        smtp = SmtpSettingsModel.query.filter_by(priority=priority).first()
        return smtp.send_per_day, smtp.send_per_month

    def send(self):
        return mail_local_sender(self.local_settings(), **send_args())


class TestMailLocalSenderFallback(SmtpFallbackTestCase):

    def test_uses_first_provider_when_it_works(self):
        before = self.counters(10), self.counters(20)

        with mock.patch.object(EmailController, 'send_mail', return_value=True) as sender:
            self.assertTrue(self.send())

        self.assertEqual(sender.call_count, 1)
        self.assertEqual(self.counters(10), (before[0][0] + 1, before[0][1] + 1))
        self.assertEqual(self.counters(20), before[1])

    def test_falls_back_to_second_provider_when_first_fails(self):
        first_before, second_before = self.counters(10), self.counters(20)

        with mock.patch.object(EmailController, 'send_mail', side_effect=[False, True]) as sender:
            self.assertTrue(self.send())

        self.assertEqual(sender.call_count, 2)
        self.assertEqual(self.counters(10), first_before)
        self.assertEqual(self.counters(20)[0], second_before[0] + 1)

    def test_fallback_tries_providers_in_priority_order(self):
        with mock.patch.object(EmailController, 'send_mail', side_effect=[False, True]) as sender:
            self.send()

        hosts = [call.args[3] for call in sender.call_args_list]
        self.assertEqual(hosts, ['smtp-relay.brevo.com', 'smtp.sendgrid.net'])

    def test_returns_false_and_rolls_back_when_all_providers_fail(self):
        first_before, second_before = self.counters(10), self.counters(20)

        with mock.patch.object(EmailController, 'send_mail', return_value=False) as sender:
            self.assertFalse(self.send())

        self.assertEqual(sender.call_count, 2)
        self.assertEqual(self.counters(10), first_before)
        self.assertEqual(self.counters(20), second_before)

    def test_does_not_retry_a_provider_that_already_succeeded(self):
        with mock.patch.object(EmailController, 'send_mail', return_value=True) as sender:
            self.send()
            self.send()

        self.assertEqual(sender.call_count, 2)
        self.assertEqual(self.counters(20)[0], 10)


class TestMailLocalSenderWithoutProviders(SmtpFallbackTestCase):
    set_smtp_settings = False

    def test_returns_false_when_there_are_no_smtp_settings(self):
        with mock.patch.object(EmailController, 'send_mail') as sender:
            self.assertFalse(self.send())

        sender.assert_not_called()


class TestSendMail(TestCase):
    """send_mail() talks SMTP; the EMAIL_TEST_MODE short-circuit is forced off and smtplib is mocked."""

    def create_app(self):
        return create_app(config_test)

    def setUp(self):
        patcher = mock.patch.object(EmailController, 'DEBUG', False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self):
        return send_mail('info@local.com', 'user', 'pass', 'smtp.example.com', 587, 'client@example.com',
                         'Subject', 'local.com', '<p>Hello</p>', 'html', 'Local')

    def test_success_logs_in_and_sends(self):
        with mock.patch.object(EmailController.smtplib, 'SMTP') as smtp:
            self.assertTrue(self.call())

        smtp.assert_called_once_with('smtp.example.com', 587)
        server = smtp.return_value
        server.starttls.assert_called_once()
        server.login.assert_called_once_with('user', 'pass')
        self.assertEqual(server.sendmail.call_args.args[:2], ('info@local.com', 'client@example.com'))
        server.quit.assert_called_once()

    def test_smtp_exception_returns_false(self):
        with mock.patch.object(EmailController.smtplib, 'SMTP', side_effect=smtplib.SMTPException('boom')):
            self.assertFalse(self.call())

    def test_authentication_error_returns_false_and_sends_nothing(self):
        with mock.patch.object(EmailController.smtplib, 'SMTP') as smtp:
            smtp.return_value.login.side_effect = smtplib.SMTPAuthenticationError(535, b'bad credentials')
            self.assertFalse(self.call())

        smtp.return_value.sendmail.assert_not_called()

    def test_connection_refused_returns_false(self):
        with mock.patch.object(EmailController.smtplib, 'SMTP', side_effect=ConnectionRefusedError()):
            self.assertFalse(self.call())

    def test_test_mode_short_circuits_without_touching_smtp(self):
        with mock.patch.object(EmailController, 'DEBUG', True), \
                mock.patch.dict('os.environ', {'EMAIL_TEST_MODE': 'True'}), \
                mock.patch.object(EmailController.smtplib, 'SMTP') as smtp:
            self.assertTrue(self.call())

        smtp.assert_not_called()
