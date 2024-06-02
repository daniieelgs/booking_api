
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import smtplib
import socket
import time
import traceback
from db import addAndCommit, rollback
from globals import DEFAULT_LOCATION_TIME, EMAIL_CANCELLED_PAGE, EMAIL_CONFIRMATION_PAGE, EMAIL_CONFIRMED_PAGE, EMAIL_UPDATED_PAGE, KEYWORDS_PAGES, DEBUG, EmailType, get_fqdn_cache, log
from helpers.DatetimeHelper import naiveToAware, now
from helpers.path import generatePagePath
from helpers.security import decrypt_str
from models.booking import BookingModel
from models.local import LocalModel
from models.local_settings import LocalSettingsModel
from models.session_token import SessionTokenModel
from models.smtp_settings import SmtpSettingsModel
from resources.public_files import generateFileResponse
from dateutil.relativedelta import relativedelta

from dotenv import load_dotenv


def generate_message_id(domain):
    return f"<{int(time.time())}.{get_fqdn_cache()}@{domain}>"

def send_mail(smtp_mail, smtp_user, smtp_passwd, smtp_host, smtp_port, to, subject, domain, content, type, name = None, _uuid = None) -> bool:

    log(f"Sending mail to {to}...", uuid=_uuid)
    log(f"Host: {smtp_host}:{smtp_port}. User: {smtp_user}. Pass: {smtp_passwd}. Subject: {subject}", uuid=_uuid)

    email = MIMEMultipart()
    email["From"] = f'{name} <{smtp_mail}>' if name else smtp_mail
    email["To"] = to
    email["Subject"] = subject
    email["Message-ID"] = generate_message_id(domain)
    
    email.attach(MIMEText(content, type))
    
    if DEBUG:
        load_dotenv()
        if os.getenv('EMAIL_TEST_MODE', 'False') == 'True':
            log("Email test mode activated.", uuid=_uuid)
            return True

    # print("Email test mode not activated.")

    try:
                
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
            
        server.login(smtp_user, smtp_passwd)
        server.sendmail(smtp_mail, to, email.as_string())
        server.quit()
        log(f"Mail sent to {to}.", uuid=_uuid)
        return True
    except Exception as e:
        log(f"FATAL ERROR. Mail not sent to {to}.", uuid=_uuid, level="ERROR", error=e)
        return False


def mail_local_sender(local_settings: LocalSettingsModel, to, subject, content, type, name, location_local = DEFAULT_LOCATION_TIME, _uuid = None) -> bool:
    
    smtp_settings = local_settings.smtp_settings.order_by(SmtpSettingsModel.priority).all()
    if not smtp_settings:
        log(f"Error. SMTP settings not found. Local: {local_settings.local.name}", uuid=_uuid, level="WARNING")
        return False
        
    for smtp in smtp_settings:
        
        max_day = smtp.max_send_per_day
        max_month = smtp.max_send_per_month
        
        date_now = now(location_local)
        
        modify_day = False
        modify_month = False
        
        if max_day:
                        
            date_reset = naiveToAware(smtp.reset_send_per_day, location_local)
            
            if date_reset <= date_now:
                smtp.send_per_day = 0
                smtp.reset_send_per_day = datetime.datetime.combine(date_now.date() + datetime.timedelta(days=1), date_reset.time())
                
            if smtp.send_per_day >= max_day:
                log(f"Error. Max send per day reached. Local: {local_settings.local.name}", uuid=_uuid, level="WARNING")
                continue
            
            smtp.send_per_day += 1
            modify_day = True
                
        if max_month:
                        
            date_reset = naiveToAware(smtp.reset_send_per_month, location_local)
            
            if date_reset <= date_now:
                smtp.send_per_month = 0
                smtp.reset_send_per_month = datetime.datetime.combine(date_now.date() + relativedelta(months=+1), date_reset.time()).replace(day=date_reset.day)
            
            if smtp.send_per_month >= max_month:
                if modify_day:
                    smtp.send_per_day -= 1
                log(f"Error. Max send per month reached. Local: {local_settings.local.name}", uuid=_uuid, level="WARNING")
                continue
        
            smtp.send_per_month += 1
            modify_month = True
            
        try:
            addAndCommit(smtp)
        except Exception as e:
            log(f"FATAL ERROR. SMTP settings not saved. Local: {local_settings.local.name}", uuid=_uuid, level="ERROR", error=e)
            traceback.print_exc()
            rollback()
            return False
        
        if send_mail(smtp.mail, smtp.user, decrypt_str(smtp.password), smtp.host, smtp.port, to, subject, local_settings.domain, content, type, name, _uuid=_uuid):
            return True
        else:
            log(f"Error. Mail not sent. Local: {local_settings.local.name}", uuid=_uuid, level="WARNING")
            if modify_day: smtp.send_per_day -= 1
            if modify_month: smtp.send_per_month -= 1
            
            try:
                addAndCommit(smtp)
            except Exception as e:
                log(f"FATAL ERROR. SMTP settings not saved. Local: {local_settings.local.name}", uuid=_uuid, level="ERROR", error=e)
                traceback.print_exc()
                rollback()
                            
    return False
    
def render_page(local: LocalModel, local_settings: LocalSettingsModel, book:BookingModel, booking_token, page): #TODO mostrar estado de la reserva
    
    confirmation_link:str = local_settings.confirmation_link if local_settings.confirmation_link is not None else ""
    confirmation_link = confirmation_link.replace(KEYWORDS_PAGES['BOOKING_TOKEN'], booking_token)

    cancel_link:str = local_settings.cancel_link if local_settings.cancel_link is not None else ""
    cancel_link = cancel_link.replace(KEYWORDS_PAGES['BOOKING_TOKEN'], booking_token)
    
    update_link:str = local_settings.update_link if local_settings.update_link is not None else ""
    update_link = cancel_link.replace(KEYWORDS_PAGES['BOOKING_TOKEN'], booking_token)
    
    client_name = book.client_name
    local_name = local.name
    date = book.datetime_init.strftime("%d/%m/%Y")
    time = book.datetime_init.strftime("%H:%M")
    comment = book.comment if book.comment is not None else ""
    service = ", ".join([service.name for service in book.services])
    cost = str(book.total_price)
    worker = book.worker.name + ((" " + book.worker.last_name ) if book.worker.last_name is not None else "")
    address_maps = local_settings.maps
    address = local.address
    phone_contact = local_settings.phone_contact
    email_contact = local_settings.email_contact
    timeout_confirm_booking = str(int(local_settings.booking_timeout / 60)) if local_settings.booking_timeout and local_settings.booking_timeout > 0 else 0
    website = local_settings.website
    whatsapp_link = local_settings.whatsapp
    
    try:
        response = generateFileResponse(local.id, generatePagePath(page))
                
        mail_body = (
                    response.get_data().decode('utf-8')
                    .replace(KEYWORDS_PAGES['CONFIRMATION_LINK'], confirmation_link)
                    .replace(KEYWORDS_PAGES['CANCEL_LINK'], cancel_link)
                    .replace(KEYWORDS_PAGES['UPDATE_LINK'], update_link)
                    .replace(KEYWORDS_PAGES['CLIENT_NAME'], client_name)
                    .replace(KEYWORDS_PAGES['LOCAL_NAME'], local_name)
                    .replace(KEYWORDS_PAGES['DATE'], date)
                    .replace(KEYWORDS_PAGES['TIME'], time)
                    .replace(KEYWORDS_PAGES['SERVICE'], service)
                    .replace(KEYWORDS_PAGES['COST'], cost)
                    .replace(KEYWORDS_PAGES['WORKER'], worker)
                    .replace(KEYWORDS_PAGES['ADDRESS-MAPS'], address_maps)
                    .replace(KEYWORDS_PAGES['ADDRESS'], address)
                    .replace(KEYWORDS_PAGES['PHONE_CONTACT'], phone_contact)
                    .replace(KEYWORDS_PAGES['EMAIL_CONTACT'], email_contact)
                    .replace(KEYWORDS_PAGES['TIMEOUT_CONFIRM_BOOKING'], str(timeout_confirm_booking))
                    .replace(KEYWORDS_PAGES['WEBSITE'], website)
                    .replace(KEYWORDS_PAGES['WHATSAPP_LINK'], whatsapp_link)
                    .replace(KEYWORDS_PAGES['COMMENT'], comment)
                    )
        subject = mail_body.split("<title>")[1].split("</title>")[0]
        
        return (mail_body, subject)
        
    except:
        if DEBUG:
            load_dotenv()
            if os.getenv('EMAIL_TEST_MODE', 'False') == 'True':
                return ("Body Mail Test Mode", "Subject Test Mode")
        traceback.print_exc()
        return False

def send_mail_booking(local: LocalModel, book:BookingModel, booking_token, page, email_type: EmailType, _uuid = None) -> bool:
    
    log(f"Sending mail. Email type: {email_type}. Local: {local.name}", uuid=_uuid)
    
    to = book.client_email
    
    local_settings = local.local_settings
    if not local_settings:
        log(f"Error. Local settings not found. Local: {local.name}", uuid=_uuid, level="WARNING")
        return False
    
    if email_type == EmailType.CONFIRM_EMAIL and (not local_settings.booking_timeout or local_settings.booking_timeout == -1): #TODO check
        log(f"Error. Timeout not found. Local: {local.name}", uuid=_uuid, level="WARNING")    
        return False
    
    log(f"Rendering page. Local: {local.name}", uuid=_uuid)
    renderPage = render_page(local, local_settings, book, booking_token, page)

    if not renderPage:
        log(f"Error. Page not found. Local: {local.name}", uuid=_uuid, level="WARNING")
        return False

    mail_body, subject = renderPage

    return mail_local_sender(local_settings, to, subject, mail_body, 'html', local.name, location_local = local.location, _uuid=_uuid)

def send_confirm_booking_mail(local: LocalModel, book:BookingModel, booking_token, _uuid = None) -> bool:
    return send_mail_booking(local, book, booking_token, EMAIL_CONFIRMATION_PAGE, EmailType.CONFIRM_EMAIL, _uuid=_uuid)

def send_confirmed_booking_mail(local: LocalModel, book: BookingModel, booking_token, _uuid = None) -> bool:
    return send_mail_booking(local, book, booking_token, EMAIL_CONFIRMED_PAGE, EmailType.CONFIRMED_EMAIL, _uuid=_uuid)

def send_cancelled_booking_mail(local: LocalModel, book: BookingModel, booking_token, _uuid = None) -> bool:
    return send_mail_booking(local, book, booking_token, EMAIL_CANCELLED_PAGE, EmailType.CANCELLED_EMAIL, _uuid=_uuid)

def send_updated_booking_mail(local: LocalModel, book: BookingModel, booking_token, _uuid = None) -> bool:
    return send_mail_booking(local, book, booking_token, EMAIL_UPDATED_PAGE, EmailType.UPDATED_EMAIL, _uuid=_uuid)