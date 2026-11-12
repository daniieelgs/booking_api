"""helpers/EmailController.py with every collaborator faked: SMTP socket, DB commits, clock and template file."""
import datetime
import email
import os
import smtplib
import unittest
from types import SimpleNamespace
from unittest import mock

import pytz

from globals import (EMAIL_CANCELLED_PAGE, EMAIL_CONFIRMATION_PAGE, EMAIL_CONFIRMED_PAGE, EMAIL_UPDATED_PAGE,
                     EmailType, KEYWORDS_PAGES)
from helpers import EmailController
from helpers.EmailController import (generate_message_id, mail_local_sender, render_page, send_mail,
                                     send_mail_booking)

MADRID = pytz.timezone('Europe/Madrid')
NOW = MADRID.localize(datetime.datetime(2030, 1, 15, 12, 0))


class FakeQuery:
    def __init__(self, items):
        self.items = items

    def order_by(self, *_):
        return self

    def all(self):
        return list(self.items)


def smtp(name='p1', **overrides):
    values = dict(name=name, mail=f'{name}@x.com', user=f'{name}-user', password=f'enc-{name}', host=f'{name}.smtp.com',
                  port=587, priority=10, max_send_per_day=None, max_send_per_month=None, send_per_day=0,
                  send_per_month=0, reset_send_per_day=None, reset_send_per_month=None)
    values.update(overrides)
    return SimpleNamespace(**values)


def settings(*providers):
    return SimpleNamespace(smtp_settings=FakeQuery(providers), local=SimpleNamespace(name='Sublime'), domain='sublime.com')


class TestGenerateMessageId(unittest.TestCase):

    def test_format(self):
        with mock.patch.object(EmailController.time, 'time', return_value=1700000000.9), \
                mock.patch.object(EmailController, 'get_fqdn_cache', return_value='host.local'):
            self.assertEqual(generate_message_id('sublime.com'), '<1700000000.host.local@sublime.com>')


class TestSendMail(unittest.TestCase):
    ARGS = ('from@x.com', 'smtp-user', 'smtp-pass', 'smtp.host.com', 587, 'to@client.com', 'Subject', 'sublime.com',
            '<p>Hola</p>', 'html')

    def run_send(self, mode='False', **kwargs):
        with mock.patch.dict(os.environ, {'EMAIL_TEST_MODE': mode}), mock.patch.object(EmailController.smtplib, 'SMTP') as client:
            result = send_mail(*self.ARGS, **kwargs)
        return result, client

    def sent_message(self, client):
        return email.message_from_string(client.return_value.sendmail.call_args.args[2])

    def test_test_mode_returns_true_without_opening_a_socket(self):
        result, client = self.run_send(mode='True')

        self.assertTrue(result)
        client.assert_not_called()

    def test_smtp_password_is_never_logged(self):
        with mock.patch.object(EmailController, 'log') as log:
            self.run_send()

        logged = ' '.join(str(c) for c in log.call_args_list)
        self.assertNotIn('smtp-pass', logged)

    def test_connects_authenticates_sends_and_quits(self):
        result, client = self.run_send()

        self.assertTrue(result)
        client.assert_called_once_with('smtp.host.com', 587)
        server = client.return_value
        server.starttls.assert_called_once_with()
        server.login.assert_called_once_with('smtp-user', 'smtp-pass')
        self.assertEqual(server.sendmail.call_args.args[:2], ('from@x.com', 'to@client.com'))
        server.quit.assert_called_once_with()

    def test_message_headers_and_body(self):
        _, client = self.run_send()

        message = self.sent_message(client)
        self.assertEqual(message['To'], 'to@client.com')
        self.assertEqual(message['Subject'], 'Subject')
        self.assertEqual(message['From'], 'from@x.com')
        self.assertTrue(message['Message-ID'].endswith('@sublime.com>'))
        self.assertEqual(message.get_payload()[0].get_content_type(), 'text/html')
        self.assertEqual(message.get_payload()[0].get_payload(decode=True), b'<p>Hola</p>')

    def test_sender_display_name(self):
        _, client = self.run_send(name='Sublime')

        self.assertEqual(self.sent_message(client)['From'], 'Sublime <from@x.com>')

    def test_plain_text_type(self):
        with mock.patch.dict(os.environ, {'EMAIL_TEST_MODE': 'False'}), mock.patch.object(EmailController.smtplib, 'SMTP') as client:
            send_mail(*self.ARGS[:-1], 'plain')

        message = email.message_from_string(client.return_value.sendmail.call_args.args[2])
        self.assertEqual(message.get_payload()[0].get_content_type(), 'text/plain')

    def test_connection_error_returns_false(self):
        with mock.patch.dict(os.environ, {'EMAIL_TEST_MODE': 'False'}), \
                mock.patch.object(EmailController.smtplib, 'SMTP', side_effect=ConnectionRefusedError):
            self.assertFalse(send_mail(*self.ARGS))

    def test_authentication_error_returns_false_and_sends_nothing(self):
        with mock.patch.dict(os.environ, {'EMAIL_TEST_MODE': 'False'}), mock.patch.object(EmailController.smtplib, 'SMTP') as client:
            client.return_value.login.side_effect = smtplib.SMTPAuthenticationError(535, b'bad credentials')

            self.assertFalse(send_mail(*self.ARGS))

        client.return_value.sendmail.assert_not_called()

    def test_rejected_recipient_returns_false(self):
        with mock.patch.dict(os.environ, {'EMAIL_TEST_MODE': 'False'}), mock.patch.object(EmailController.smtplib, 'SMTP') as client:
            client.return_value.sendmail.side_effect = smtplib.SMTPRecipientsRefused({'to@client.com': (550, b'no')})

            self.assertFalse(send_mail(*self.ARGS))


class SenderTestCase(unittest.TestCase):
    """mail_local_sender with a frozen clock; `sent` is the fake SMTP send."""

    def setUp(self):
        for name, value in dict(now=mock.Mock(return_value=NOW), addAndCommit=mock.DEFAULT, rollback=mock.DEFAULT,
                                send_mail=mock.DEFAULT, decrypt_str=mock.Mock(side_effect=lambda x: f'plain-{x}')).items():
            patcher = mock.patch.object(EmailController, name, value)
            started = patcher.start()
            self.addCleanup(patcher.stop)
            setattr(self, {'now': 'clock', 'addAndCommit': 'commit', 'rollback': 'rollback', 'send_mail': 'sent',
                           'decrypt_str': 'decrypt'}[name], started)
        self.sent.return_value = True

    def send(self, *providers, **kwargs):
        return mail_local_sender(settings(*providers), 'to@client.com', 'Subject', '<p>Hi</p>', 'html', 'Sublime', **kwargs)


class TestMailLocalSender(SenderTestCase):

    def test_no_providers_returns_false_without_sending(self):
        self.assertFalse(self.send())

        self.sent.assert_not_called()

    def test_first_provider_is_used_with_its_decrypted_password(self):
        p1, p2 = smtp('p1'), smtp('p2')

        self.assertTrue(self.send(p1, p2))

        self.sent.assert_called_once_with('p1@x.com', 'p1-user', 'plain-enc-p1', 'p1.smtp.com', 587, 'to@client.com',
                                          'Subject', 'sublime.com', '<p>Hi</p>', 'html', 'Sublime', _uuid=None)

    def test_falls_back_to_the_next_provider_when_one_fails(self):
        self.sent.side_effect = [False, True]
        p1, p2 = smtp('p1'), smtp('p2')

        self.assertTrue(self.send(p1, p2))

        self.assertEqual([c.args[3] for c in self.sent.call_args_list], ['p1.smtp.com', 'p2.smtp.com'])

    def test_returns_false_when_every_provider_fails(self):
        self.sent.return_value = False

        self.assertFalse(self.send(smtp('p1'), smtp('p2')))

        self.assertEqual(self.sent.call_count, 2)

    def test_location_is_used_to_read_the_clock(self):
        self.send(smtp('p1'), location_local='America/Mexico_City')

        self.clock.assert_called_with('America/Mexico_City')

    def test_database_failure_aborts_without_sending(self):
        self.commit.side_effect = RuntimeError('db down')

        self.assertFalse(self.send(smtp('p1')))

        self.sent.assert_not_called()
        self.rollback.assert_called_once_with()


class TestDailyQuota(SenderTestCase):
    FUTURE = datetime.datetime(2030, 1, 16, 0, 0)

    def test_successful_send_counts_one(self):
        p = smtp(max_send_per_day=10, send_per_day=3, reset_send_per_day=self.FUTURE)

        self.assertTrue(self.send(p))

        self.assertEqual(p.send_per_day, 4)

    def test_failed_send_gives_the_count_back(self):
        self.sent.return_value = False
        p = smtp(max_send_per_day=10, send_per_day=3, reset_send_per_day=self.FUTURE)

        self.send(p)

        self.assertEqual(p.send_per_day, 3)

    def test_provider_at_its_daily_cap_is_skipped(self):
        full = smtp('full', max_send_per_day=5, send_per_day=5, reset_send_per_day=self.FUTURE)
        spare = smtp('spare')

        self.assertTrue(self.send(full, spare))

        self.assertEqual(full.send_per_day, 5)
        self.assertEqual(self.sent.call_args.args[3], 'spare.smtp.com')

    def test_every_provider_at_its_cap_returns_false(self):
        full = smtp(max_send_per_day=5, send_per_day=5, reset_send_per_day=self.FUTURE)

        self.assertFalse(self.send(full))

        self.sent.assert_not_called()

    def test_counter_resets_when_the_reset_time_has_passed(self):
        p = smtp(max_send_per_day=5, send_per_day=5, reset_send_per_day=datetime.datetime(2030, 1, 15, 0, 0))

        self.assertTrue(self.send(p))

        self.assertEqual(p.send_per_day, 1)
        self.assertEqual(p.reset_send_per_day, datetime.datetime(2030, 1, 16, 0, 0))

    def test_counter_is_kept_before_the_reset_time(self):
        p = smtp(max_send_per_day=5, send_per_day=2, reset_send_per_day=self.FUTURE)

        self.send(p)

        self.assertEqual(p.send_per_day, 3)
        self.assertEqual(p.reset_send_per_day, self.FUTURE)

    def test_no_cap_means_no_counting(self):
        p = smtp(max_send_per_day=None, send_per_day=7)

        self.send(p)

        self.assertEqual(p.send_per_day, 7)

    def test_cap_without_a_reset_date_does_not_crash(self):
        # the schema lets a provider have max_send_per_day without reset_send_per_day
        p = smtp(max_send_per_day=5, reset_send_per_day=None)

        self.assertTrue(self.send(p))


class TestMonthlyQuota(SenderTestCase):
    FUTURE = datetime.datetime(2030, 2, 1, 0, 0)

    def test_successful_send_counts_one(self):
        p = smtp(max_send_per_month=100, send_per_month=10, reset_send_per_month=self.FUTURE)

        self.assertTrue(self.send(p))

        self.assertEqual(p.send_per_month, 11)

    def test_failed_send_gives_the_count_back(self):
        self.sent.return_value = False
        p = smtp(max_send_per_month=100, send_per_month=10, reset_send_per_month=self.FUTURE)

        self.send(p)

        self.assertEqual(p.send_per_month, 10)

    def test_provider_at_its_monthly_cap_is_skipped(self):
        full = smtp('full', max_send_per_month=100, send_per_month=100, reset_send_per_month=self.FUTURE)
        spare = smtp('spare')

        self.assertTrue(self.send(full, spare))

        self.assertEqual(self.sent.call_args.args[3], 'spare.smtp.com')

    def test_monthly_cap_hit_after_the_daily_check_gives_the_day_back(self):
        p = smtp(max_send_per_day=10, send_per_day=3, reset_send_per_day=datetime.datetime(2030, 1, 16),
                 max_send_per_month=100, send_per_month=100, reset_send_per_month=self.FUTURE)

        self.assertFalse(self.send(p))

        self.assertEqual(p.send_per_day, 3)

    def test_counter_resets_a_month_later_on_the_same_day(self):
        p = smtp(max_send_per_month=100, send_per_month=100, reset_send_per_month=datetime.datetime(2030, 1, 10, 0, 0))

        self.assertTrue(self.send(p))

        self.assertEqual(p.send_per_month, 1)
        self.assertEqual(p.reset_send_per_month, datetime.datetime(2030, 2, 10, 0, 0))

    def test_reset_on_the_31st_does_not_crash_in_a_shorter_month(self):
        self.clock.return_value = MADRID.localize(datetime.datetime(2030, 1, 31, 12, 0))
        p = smtp(max_send_per_month=100, send_per_month=100, reset_send_per_month=datetime.datetime(2030, 1, 31, 0, 0))

        self.assertTrue(self.send(p))

        self.assertGreater(p.reset_send_per_month, datetime.datetime(2030, 1, 31, 12, 0))

    def test_cap_without_a_reset_date_does_not_crash(self):
        p = smtp(max_send_per_month=100, reset_send_per_month=None)

        self.assertTrue(self.send(p))


class TestNextQuotaReset(unittest.TestCase):
    NOW = MADRID.localize(datetime.datetime(2030, 1, 15, 12, 0))

    def day(self, k):
        return datetime.timedelta(days=k)

    def month(self, k):
        return EmailController.relativedelta(months=+k)

    def test_missing_reset_starts_one_step_from_now_and_keeps_the_counter(self):
        self.assertEqual(EmailController.next_quota_reset(None, self.NOW, self.day), (datetime.datetime(2030, 1, 16, 12, 0), False))

    def test_future_reset_is_unchanged(self):
        future = datetime.datetime(2030, 1, 20)
        self.assertEqual(EmailController.next_quota_reset(future, self.NOW, self.day), (future, False))

    def test_daily_reset_long_overdue_lands_on_the_next_future_occurrence(self):
        self.assertEqual(EmailController.next_quota_reset(datetime.datetime(2030, 1, 10, 0, 0), self.NOW, self.day),
                         (datetime.datetime(2030, 1, 16, 0, 0), True))

    def test_monthly_reset_on_the_31st_clips_in_short_months_but_keeps_day_31_after(self):
        in_february = MADRID.localize(datetime.datetime(2030, 2, 1, 9, 0))
        self.assertEqual(EmailController.next_quota_reset(datetime.datetime(2030, 1, 31), in_february, self.month),
                         (datetime.datetime(2030, 2, 28), True))
        in_march = MADRID.localize(datetime.datetime(2030, 3, 1, 9, 0))
        self.assertEqual(EmailController.next_quota_reset(datetime.datetime(2030, 1, 31), in_march, self.month),
                         (datetime.datetime(2030, 3, 31), True))


def render_context(**overrides):
    local = SimpleNamespace(id='local-1', name='Sublime', address='Calle Mayor 1')
    local_settings = SimpleNamespace(
        confirmation_link='https://web.com/confirm/' + KEYWORDS_PAGES['BOOKING_TOKEN'],
        cancel_link='https://web.com/cancel/' + KEYWORDS_PAGES['BOOKING_TOKEN'],
        update_link='https://web.com/update/' + KEYWORDS_PAGES['BOOKING_TOKEN'],
        maps='https://maps.com/x', phone_contact='600000000', email_contact='info@sublime.com',
        booking_timeout=120, website='https://sublime.com', whatsapp='https://wa.me/1')
    book = SimpleNamespace(
        client_name='Daniel', datetime_init=datetime.datetime(2030, 1, 5, 16, 30), comment='Sin prisa',
        services=[SimpleNamespace(name='Corte'), SimpleNamespace(name='Barba')], total_price=25.5,
        worker=SimpleNamespace(name='Ana', last_name='Perez'), uuid_log='uuid-1')
    for target, values in overrides.items():
        for key, value in values.items():
            setattr({'local': local, 'settings': local_settings, 'book': book}[target], key, value)
    return local, local_settings, book


def template(*keys):
    body = '|'.join(KEYWORDS_PAGES[k] for k in keys)
    return f'<html><head><title>Reserva {KEYWORDS_PAGES["LOCAL_NAME"]}</title></head><body>{body}</body></html>'


class TestRenderPage(unittest.TestCase):

    def render(self, *keys, html=None, **overrides):
        local, local_settings, book = render_context(**overrides)
        response = SimpleNamespace(get_data=lambda: (html if html is not None else template(*keys)).encode('utf-8'))
        with mock.patch.dict(os.environ, {'EMAIL_TEST_MODE': 'False'}), \
                mock.patch.object(EmailController, 'generateFileResponse', return_value=response) as files:
            result = render_page(local, local_settings, book, 'TOKEN123', 'email_confirmed.html')
        self.files = files
        return result

    def body(self, *keys, **overrides):
        return self.render(*keys, **overrides)[0].split('<body>')[1].split('</body>')[0]

    def test_returns_body_and_subject_taken_from_the_title(self):
        body, subject = self.render('CLIENT_NAME')

        self.assertEqual(subject, 'Reserva Sublime')
        self.assertIn('Daniel', body)

    def test_reads_the_template_of_that_local_and_page(self):
        self.render('CLIENT_NAME')

        args = self.files.call_args.args
        self.assertEqual(args[0], 'local-1')
        self.assertTrue(args[1].endswith('email_confirmed.html'))

    def test_booking_fields(self):
        self.assertEqual(self.body('DATE', 'TIME', 'SERVICE', 'COST', 'WORKER', 'COMMENT', 'UUID_LOG'),
                         '05/01/2030|16:30|Corte, Barba|25.5|Ana Perez|Sin prisa|uuid-1')

    def test_local_fields(self):
        self.assertEqual(self.body('LOCAL_NAME', 'ADDRESS', 'ADDRESS-MAPS', 'PHONE_CONTACT', 'EMAIL_CONTACT', 'WEBSITE', 'WHATSAPP_LINK'),
                         'Sublime|Calle Mayor 1|https://maps.com/x|600000000|info@sublime.com|https://sublime.com|https://wa.me/1')

    def test_confirmation_and_cancel_links_carry_the_token(self):
        self.assertEqual(self.body('CONFIRMATION_LINK', 'CANCEL_LINK'),
                         'https://web.com/confirm/TOKEN123|https://web.com/cancel/TOKEN123')

    def test_update_link_uses_the_update_url_with_the_token(self):
        self.assertEqual(self.body('UPDATE_LINK'), 'https://web.com/update/TOKEN123')

    def test_worker_without_last_name(self):
        self.assertEqual(self.body('WORKER', book={'worker': SimpleNamespace(name='Ana', last_name=None)}), 'Ana')

    def test_missing_comment_renders_empty(self):
        self.assertEqual(self.body('COMMENT', book={'comment': None}), '')

    def test_missing_links_render_empty(self):
        self.assertEqual(self.body('CONFIRMATION_LINK', 'CANCEL_LINK', settings={'confirmation_link': None, 'cancel_link': None}), '|')

    def test_timeout_is_shown_in_hours(self):
        self.assertEqual(self.body('TIMEOUT_CONFIRM_BOOKING', settings={'booking_timeout': 120}), '2')

    def test_disabled_timeout_renders_zero(self):
        for value in (None, -1, 0):
            with self.subTest(value=value):
                self.assertEqual(self.body('TIMEOUT_CONFIRM_BOOKING', settings={'booking_timeout': value}), '0')

    def test_optional_settings_left_empty_still_render(self):
        # maps/website/whatsapp/phone/email are optional in the schema; a missing one must not abort the email
        result = self.render('ADDRESS-MAPS', 'WEBSITE', 'WHATSAPP_LINK', 'PHONE_CONTACT', 'EMAIL_CONTACT',
                             settings={'maps': None, 'website': None, 'whatsapp': None, 'phone_contact': None,
                                       'email_contact': None})

        self.assertIsNot(result, False)
        self.assertEqual(result[0].split('<body>')[1].split('</body>')[0], '||||')

    def test_template_without_a_title_returns_false(self):
        self.assertFalse(self.render(html='<html><body>no title</body></html>'))

    def test_missing_template_file_returns_false(self):
        local, local_settings, book = render_context()
        with mock.patch.dict(os.environ, {'EMAIL_TEST_MODE': 'False'}), \
                mock.patch.object(EmailController, 'generateFileResponse', side_effect=FileNotFoundError):
            self.assertFalse(render_page(local, local_settings, book, 'T', 'email_confirmed.html'))

    def test_missing_template_file_in_test_mode_returns_the_placeholders(self):
        local, local_settings, book = render_context()
        with mock.patch.dict(os.environ, {'EMAIL_TEST_MODE': 'True'}), \
                mock.patch.object(EmailController, 'generateFileResponse', side_effect=FileNotFoundError):
            self.assertEqual(render_page(local, local_settings, book, 'T', 'email_confirmed.html'),
                             ('Body Mail Test Mode', 'Subject Test Mode'))


class TestSendMailBooking(unittest.TestCase):

    def setUp(self):
        self.render = self.patch('render_page', return_value=('<p>body</p>', 'The subject'))
        self.sender = self.patch('mail_local_sender', return_value=True)
        self.settings = SimpleNamespace(booking_timeout=60)
        self.local = SimpleNamespace(name='Sublime', location='Europe/Madrid', local_settings=self.settings)
        self.book = SimpleNamespace(client_email='client@x.com')

    def patch(self, name, **kwargs):
        patcher = mock.patch.object(EmailController, name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def send(self, email_type=EmailType.CONFIRMED_EMAIL):
        return send_mail_booking(self.local, self.book, 'TOKEN', 'page.html', email_type, _uuid='u-1')

    def test_renders_then_sends_to_the_client(self):
        self.assertTrue(self.send())

        self.render.assert_called_once_with(self.local, self.settings, self.book, 'TOKEN', 'page.html')
        self.sender.assert_called_once_with(self.settings, 'client@x.com', 'The subject', '<p>body</p>', 'html', 'Sublime',
                                            location_local='Europe/Madrid', _uuid='u-1')

    def test_local_without_settings_returns_false(self):
        self.local.local_settings = None

        self.assertFalse(self.send())

        self.sender.assert_not_called()

    def test_confirmation_email_needs_a_booking_timeout(self):
        for value in (None, -1, 0):
            with self.subTest(timeout=value):
                self.settings.booking_timeout = value

                self.assertFalse(self.send(EmailType.CONFIRM_EMAIL))

        self.sender.assert_not_called()

    def test_confirmation_email_is_sent_when_there_is_a_timeout(self):
        self.assertTrue(self.send(EmailType.CONFIRM_EMAIL))

    def test_other_emails_do_not_need_a_timeout(self):
        self.settings.booking_timeout = None
        for email_type in (EmailType.CONFIRMED_EMAIL, EmailType.CANCELLED_EMAIL, EmailType.UPDATED_EMAIL):
            with self.subTest(type=email_type):
                self.assertTrue(self.send(email_type))

    def test_unrenderable_page_returns_false(self):
        self.render.return_value = False

        self.assertFalse(self.send())

        self.sender.assert_not_called()

    def test_returns_what_the_sender_returns(self):
        self.sender.return_value = False

        self.assertFalse(self.send())


class TestBookingMailWrappers(unittest.TestCase):

    def test_each_wrapper_picks_its_page_and_type(self):
        cases = [
            (EmailController.send_confirm_booking_mail, EMAIL_CONFIRMATION_PAGE, EmailType.CONFIRM_EMAIL),
            (EmailController.send_confirmed_booking_mail, EMAIL_CONFIRMED_PAGE, EmailType.CONFIRMED_EMAIL),
            (EmailController.send_cancelled_booking_mail, EMAIL_CANCELLED_PAGE, EmailType.CANCELLED_EMAIL),
            (EmailController.send_updated_booking_mail, EMAIL_UPDATED_PAGE, EmailType.UPDATED_EMAIL),
        ]
        for wrapper, page, email_type in cases:
            with self.subTest(wrapper=wrapper.__name__), mock.patch.object(EmailController, 'send_mail_booking', return_value=True) as sender:
                self.assertTrue(wrapper('local', 'book', 'TOKEN', _uuid='u-1'))

                sender.assert_called_once_with('local', 'book', 'TOKEN', page, email_type, _uuid='u-1')


if __name__ == '__main__':
    unittest.main()
