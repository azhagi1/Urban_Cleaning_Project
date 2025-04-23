import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

# Load from .env
load_dotenv()

# Email Config
EMAIL_SENDER = os.getenv('EMAIL_SENDER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))

# Flask Secret Key
SECRET_KEY = os.getenv('SECRET_KEY')

# Database Connection
def create_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=3306,
            connect_timeout=20
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Connection error: {e}")
        return None
