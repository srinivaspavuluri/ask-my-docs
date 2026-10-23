import psycopg2
from app.config import DB_HOST, DB_NAME, DB_PORT, DB_PASSWORD, DB_USER

def get_db_connection():
    db_connection = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )
    return db_connection
