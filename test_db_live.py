import os
import psycopg2
import json

DB_URL = "postgresql://postgres:IyvjQcfmReamkaOGSguxUvBhCirdXuHA@switchyard.proxy.rlwy.net:11701/railway"

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()
cursor.execute("SELECT payload FROM plans ORDER BY user_id DESC LIMIT 1;")
rows = cursor.fetchall()
if not rows:
    print("No plans generated.")
else:
    for row in rows:
        payload = row[0]
        subtemas = payload.get("trilha_subtemas", [])
        print(f"Total subtemas gerados na trilha: {len(subtemas)}")
        for st in subtemas:
            print(f"- {st.get('tema')}")
        print("===")
cursor.close()
conn.close()
