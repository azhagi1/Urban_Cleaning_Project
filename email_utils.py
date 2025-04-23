import smtplib
import random
from email.message import EmailMessage
from config import EMAIL_SENDER, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT

def generate_code():
    return str(random.randint(100000, 999999))

def send_verification_code(email, code):
    msg = EmailMessage()
    msg.set_content(f"Your verification code is: {code}")
    msg['Subject'] = 'Email Verification Code'
    msg['From'] = EMAIL_SENDER
    msg['To'] = email

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
