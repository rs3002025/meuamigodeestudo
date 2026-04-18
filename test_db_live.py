import os
import psycopg2
import json

DB_URL = "postgresql://postgres:IyvjQcfmReamkaOGSguxUvBhCirdXuHA@switchyard.proxy.rlwy.net:11701/railway"

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()
cursor.execute("SELECT payload FROM tasks;")
rows = cursor.fetchall()
if not rows:
    print("No tasks generated. This is normal if OpenAI key is missing in tests.")
else:
    for row in rows:
        tasks = row[0]
        print(f"Total tasks in UI: {len(tasks)}")
        for t in tasks:
            print(f"- {t.get('tema')} ({t.get('tipo')})")
        print("===")
cursor.close()
conn.close()
