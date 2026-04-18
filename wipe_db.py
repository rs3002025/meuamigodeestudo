import psycopg2

DB_URL = "postgresql://postgres:IyvjQcfmReamkaOGSguxUvBhCirdXuHA@switchyard.proxy.rlwy.net:11701/railway"

def wipe_db():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE tasks, plans CASCADE;")
    cursor.close()
    conn.close()
    print("DB reset complete.")

if __name__ == "__main__":
    wipe_db()
