import psycopg2
import json

DB_URL = "postgresql://postgres:IyvjQcfmReamkaOGSguxUvBhCirdXuHA@switchyard.proxy.rlwy.net:11701/railway"

def check():
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT payload FROM plans;")
    rows = cursor.fetchall()
    for row in rows:
        payload = row[0]
        print(f"Objetivo/Materia: {payload.get('objetivo')} / {payload.get('materias')}")
        subtemas = payload.get("trilha_subtemas", [])
        print(f"Number of subtemas: {len(subtemas)}")
        for st in subtemas:
            print(f" - {st.get('tema')}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    check()
