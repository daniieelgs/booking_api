
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import socket
import time
import traceback
from db import addAndCommit, rollback
from globals import DEFAULT_LOCATION_TIME, EMAIL_CONFIRMATION_PAGE, KEYWORDS_PAGES
from helpers.DatetimeHelper import naiveToAware, now
from helpers.path import generatePagePath
from helpers.security import decrypt_str
from models.booking import BookingModel
from models.local import LocalModel
from models.local_settings import LocalSettingsModel
from models.smtp_settings import SmtpSettingsModel
from resources.public_files import generateFileResponse
from dateutil.relativedelta import relativedelta


def generate_message_id(domain):
    return f"<{int(time.time())}.{socket.getfqdn()}@{domain}>"

def send_mail(smtp_mail, smtp_user, smtp_passwd, smtp_host, smtp_port, to, subject, domain, content, type) -> bool:

    print(f"Sending mail to {to}...")
    print(f"Host: {smtp_host}:{smtp_port}")
    print(f"User: {smtp_user}")
    print(f"Pass: {smtp_passwd}")
    print(f"Subject: {subject}")

    email = MIMEMultipart()
    email["From"] = smtp_mail
    email["To"] = to
    email["Subject"] = subject
    email["Message-ID"] = generate_message_id(domain)

    email.attach(MIMEText(content, type))

    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
            
        server.login(smtp_user, smtp_passwd)
        server.sendmail(smtp_mail, to, email.as_string())
        server.quit()
        now = time.strftime("%c")
        return True
    except Exception as e:
        print(f"Error al enviar el correo: {e}")
        return False


def mail_local_sender(local_settings: LocalSettingsModel, to, subject, content, type, location_local = DEFAULT_LOCATION_TIME) -> bool:
    
    smtp_settings = local_settings.smtp_settings.order_by(SmtpSettingsModel.priority).all()
    if not smtp_settings: return False
        
    for smtp in smtp_settings:
        
        max_day = smtp.max_send_per_day
        max_month = smtp.max_send_per_month
        
        date_now = now(location_local)
        
        if max_day:
            
            date_reset = naiveToAware(smtp.reset_send_per_day, location_local)
            
            if date_reset <= date_now:
                smtp.send_per_day = 0
                smtp.reset_send_per_day = date_reset + datetime.timedelta(days=1)
                
            if smtp.send_per_day >= max_day: continue
            
            smtp.send_per_day += 1
                
        if max_month:
            
            date_reset = naiveToAware(smtp.reset_send_per_month, location_local)
            
            if date_reset <= date_now:
                smtp.send_per_month = 0
                smtp.reset_send_per_month = date_reset + relativedelta(months=+1)
            
            if smtp.send_per_month >= smtp.max_send_per_month: continue
        
            smtp.send_per_month += 1
            
        try:
            addAndCommit(smtp)
        except:
            traceback.print_exc()
            rollback()
            return False
        
        if send_mail(smtp.mail, smtp.user, decrypt_str(smtp.password), smtp.host, smtp.port, to, subject, local_settings.domain, content, type):
            return True
        else:
            
            if max_day: smtp.send_per_day -= 1
            if max_month: smtp.send_per_month -= 1
            
            try:
                addAndCommit(smtp)
            except:
                traceback.print_exc()
                rollback()
                            
    return False
    

def send_confirm_booking_mail(local: LocalModel, book:BookingModel, booking_token) -> bool:
    to = book.client_email
    
    local_settings = local.local_settings
    if not local_settings: return False
    
    confirmation_link:str = local_settings.confirmation_link
    if not confirmation_link: return False
    confirmation_link = confirmation_link.replace(KEYWORDS_PAGES['BOOKING_TOKEN'], booking_token)

    cancel_link:str = local_settings.cancel_link
    if not cancel_link: return False
    cancel_link = cancel_link.replace(KEYWORDS_PAGES['BOOKING_TOKEN'], booking_token)
    
    client_name = book.client_name
    local_name = local.name
    date = book.datetime_init.strftime("%d/%m/%Y")
    time = book.datetime_init.strftime("%H:%M")
    service = ", ".join([service.name for service in book.services])
    cost = str(book.total_price)
    address_maps = local_settings.maps
    address = local.address
    phone_contact = local_settings.phone_contact
    email_contact = local_settings.email_contact
    timeout_confirm_booking = str(int(local_settings.booking_timeout / 60))
    website = local_settings.website
    whatsapp_link = local_settings.whatsapp

    try:    
        response = generateFileResponse(local.id, generatePagePath(EMAIL_CONFIRMATION_PAGE))
            
        mail_body = response.get_data().decode('utf-8').replace(KEYWORDS_PAGES['CONFIRMATION_LINK'], confirmation_link).replace(KEYWORDS_PAGES['CANCEL_LINK'], cancel_link).replace(KEYWORDS_PAGES['CLIENT_NAME'], client_name).replace(KEYWORDS_PAGES['LOCAL_NAME'], local_name).replace(KEYWORDS_PAGES['DATE'], date).replace(KEYWORDS_PAGES['TIME'], time).replace(KEYWORDS_PAGES['SERVICE'], service).replace(KEYWORDS_PAGES['COST'], cost).replace(KEYWORDS_PAGES['ADDRESS-MAPS'], address_maps).replace(KEYWORDS_PAGES['ADDRESS'], address).replace(KEYWORDS_PAGES['PHONE_CONTACT'], phone_contact).replace(KEYWORDS_PAGES['EMAIL_CONTACT'], email_contact).replace(KEYWORDS_PAGES['TIMEOUT_CONFIRM_BOOKING'], str(timeout_confirm_booking)).replace(KEYWORDS_PAGES['WEBSITE'], website).replace(KEYWORDS_PAGES['WHATSAPP_LINK'], whatsapp_link)
        subject = mail_body.split("<title>")[1].split("</title>")[0]
        
        return mail_local_sender(local_settings, to, subject, mail_body, 'html', location_local = local.location)
    except:
        traceback.print_exc()
        return False