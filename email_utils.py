import smtplib
import random

def generate_code():
    return str(random.randint(100000, 999999))

# email_utils.py

import smtplib
from email.mime.text import MIMEText

def send_verification_code(email, code):
    sender_email = "urbancleaning20@gmail.com"
    sender_password = "gqqs pipw qvzn awxd"  # Use App Password

    subject = "Your OTP Verification Code"
    body = f"Your verification code is: {code}"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = email

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, email, msg.as_string())
        server.quit()
        print("Email sent successfully")
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
        server.login('urbancleaning20@gmail.com', 'gqqs pipw qvzn awxd')
        server.send_message(msg)

