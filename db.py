
import pymysql
try:
    conn = pymysql.connect(
        host="mydb.c1q2w4gis34j.ap-south-1.rds.amazonaws.com",
        user="admin",
        password="Sreenithi123",
        database="urban_cleaning",
        port=3306
    )
    print("Connection successful")
    conn.close()
except Exception as e:
    print("Connection failed:", e)
