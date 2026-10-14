import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

host = os.getenv('DB_HOST', 'localhost')
port = os.getenv('DB_PORT', '5432')
dbname = os.getenv('DB_NAME', 'heatwave_db')
user = os.getenv('DB_USER', 'postgres')
password = os.getenv('DB_PASSWORD', 'postgres')

print(f"Connecting to: {user}@{host}:{port}/{dbname}...")

try:
    conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    tables = cur.fetchall()
    print("Tables found in database:", [t[0] for t in tables])
    for t in tables:
        cur.execute(f"SELECT count(*) FROM {t[0]};")
        cnt = cur.fetchone()[0]
        print(f"  - {t[0]}: {cnt} rows")
except Exception as e:
    print("CONNECTION / QUERY ERROR:", e)
