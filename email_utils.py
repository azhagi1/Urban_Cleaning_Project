import smtplib
import random

def generate_code():
    return str(random.randint(100000, 999999))

# email_utils.py

import smtplib
from email.mime.text import MIMEText

def send_verification_code(to_email, code):
    sender_email = "neatnestcleaningservice1.0@gmail.com"
    sender_password = "kcww zbfo hhkc ygkq"  # App password, not Gmail password

    subject = "NeatNest Email Verification Code"
    body = f"Your verification code is: {code}"

    message = MIMEText(body)
    message['From'] = sender_email
    message['To'] = to_email
    message['Subject'] = subject

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)  # TLS port
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, message.as_string())
        server.quit()
    except Exception as e:
        print("Error sending email:", e)


def send_reset_link(email, reset_link):
    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(f"Click the link to reset your password: {reset_link}")
    msg['Subject'] = 'Reset your password'
    msg['From'] = 'your-email@example.com'
    msg['To'] = email

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login('neatnestcleaningservice1.0@gmail.com', 'kcww zbfo hhkc ygkq')
        server.send_message(msg)

