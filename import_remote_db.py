"""
Helper script to import janpulse_cloud_backup.sql into a remote free cloud database (e.g. Aiven, TiDB Cloud, etc.)
Usage:
    python import_remote_db.py
"""
import os
import pymysql
from dotenv import load_dotenv

load_dotenv('.env', override=True)

host = input("Enter Cloud Database Host: ").strip() or os.getenv('DB_HOST')
port = int(input("Enter Cloud Database Port (default 3306): ").strip() or os.getenv('DB_PORT', 3306))
user = input("Enter Cloud Database User: ").strip() or os.getenv('DB_USER')
password = input("Enter Cloud Database Password: ").strip() or os.getenv('DB_PASSWORD')
dbname = input("Enter Cloud Database Name: ").strip() or os.getenv('DB_NAME')

print(f"\nConnecting to {user}@{host}:{port}/{dbname} ...")

try:
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=dbname,
        autocommit=True
    )
    print("Connected successfully!")
    
    with open('janpulse_cloud_backup.sql', 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Split by statements
    statements = sql_content.split(';')
    with conn.cursor() as cur:
        count = 0
        for stmt in statements:
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
                count += 1
    print(f"Success! Executed {count} SQL statements. Cloud database is now 100% ready!")
except Exception as e:
    print(f"Error connecting or importing: {e}")
