import psycopg2
import os

DB_URL = "postgresql://postgres:IyvjQcfmReamkaOGSguxUvBhCirdXuHA@switchyard.proxy.rlwy.net:11701/railway"

def wipe_db():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cursor = conn.cursor()
    print("Clearing tables...")
    cursor.execute("TRUNCATE TABLE tasks, plans CASCADE;")
    print("Database cleared.")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    wipe_db()
