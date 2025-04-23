import pymysql
import os

def get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "mydb.c1q2w4gis34j.ap-south-1.rds.amazonaws.com"),
        user=os.getenv("DB_USER", "admin"),
        password=os.getenv("DB_PASSWORD", "Sreenithi123"),
        database=os.getenv("DB_NAME", "mydb"),
        cursorclass=pymysql.cursors.DictCursor
    )
