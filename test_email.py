import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import socket

def generar_message_id(domain):
    # Genera un identificador único para el Message-ID
    return f"<{int(time.time())}.{socket.getfqdn()}@{domain}>"

# Configura las credenciales y los parámetros del servidor SMTP
usuario = "no-reply@sublimebarberia.com"
contraseña = "Daniarreglaelback0"
servidor_smtp = "smtp.servidor-correo.net"
puerto = 587

# Configura los detalles del correo electrónico
destinatario = "daniieelgs@gmail.com"
asunto = "Asunto del correo"
mensaje = "Este es el cuerpo del correo."

# Crea un objeto MIMEMultipart y añade los detalles
correo = MIMEMultipart()
correo["From"] = usuario
correo["To"] = destinatario
correo["Subject"] = asunto
correo["Message-ID"] = generar_message_id("sublimebarberia.com")  # Asegúrate de usar un dominio válido

# Opcional: Añadir In-Reply-To y References para respuestas
# correo["In-Reply-To"] = "<ID del mensaje original>"
# correo["References"] = "<ID del mensaje original>"

correo.attach(MIMEText(mensaje, "plain"))

# Inicia la conexión al servidor SMTP y envía el correo
try:
    server = smtplib.SMTP(servidor_smtp, puerto)
    server.starttls()
    server.login(usuario, contraseña)
    server.sendmail(usuario, destinatario, correo.as_string())
    server.quit()
    print("Correo enviado exitosamente.")
except Exception as e:
    print(f"Error al enviar el correo: {e}")
