import pymysql
import os

def get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "your-rds-endpoint.amazonaws.com"),
        user=os.getenv("DB_USER", "your-db-username"),
        password=os.getenv("DB_PASSWORD", "your-secure-password"),
        database=os.getenv("DB_NAME", "retail_store"),
        cursorclass=pymysql.cursors.DictCursor
    )
