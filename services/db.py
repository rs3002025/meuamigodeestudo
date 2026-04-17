import json
import os
from datetime import date, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada.")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def init_db():
    if not DATABASE_URL:
        return
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Users / Metrics table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(255) PRIMARY KEY,
                    dias_consecutivos INTEGER DEFAULT 0,
                    ultimo_dia_estudo DATE,
                    ultima_taxa_acerto FLOAT,
                    dias_sem_estudar INTEGER DEFAULT 0,
                    ia_geracoes_por_dia JSONB DEFAULT '{}'::jsonb
                )
            """)
            # Plans table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS plans (
                    user_id VARCHAR(255) PRIMARY KEY REFERENCES users(id),
                    payload JSONB NOT NULL
                )
            """)
            # Tasks table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) REFERENCES users(id),
                    data_ref DATE NOT NULL,
                    payload JSONB NOT NULL
                )
            """)
            # Cache table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS content_cache (
                    cache_key VARCHAR(512) PRIMARY KEY,
                    payload JSONB NOT NULL
                )
            """)
        conn.commit()

# Initialize DB on import
try:
    init_db()
except Exception as e:
    print(f"Error initializing DB: {e}")

def _hoje_utc() -> date:
    return date.today()

def get_user_metrics(user_id: str) -> dict[str, Any]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                row["ia_geracoes_por_dia"] = row["ia_geracoes_por_dia"] or {}
                return row

            cur.execute(
                "INSERT INTO users (id, ia_geracoes_por_dia) VALUES (%s, '{}'::jsonb) RETURNING *",
                (user_id,)
            )
            conn.commit()
            return cur.fetchone()

def registrar_estudo(user_id: str, studied_on: date | None = None) -> dict[str, Any]:
    hoje = studied_on or _hoje_utc()
    metrics = get_user_metrics(user_id)

    ultimo = metrics.get("ultimo_dia_estudo")
    dias_consecutivos = metrics.get("dias_consecutivos", 0)

    if ultimo == hoje:
        dias_sem_estudar = 0
    elif ultimo == (hoje - timedelta(days=1)):
        dias_consecutivos += 1
        dias_sem_estudar = 0
    else:
        dias_consecutivos = 1
        dias_sem_estudar = 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users
                SET dias_consecutivos = %s, ultimo_dia_estudo = %s, dias_sem_estudar = %s
                WHERE id = %s RETURNING *
            """, (dias_consecutivos, hoje, dias_sem_estudar, user_id))
            conn.commit()
            return cur.fetchone()

def atualizar_dias_sem_estudar(user_id: str, ref_day: date | None = None) -> dict[str, Any]:
    hoje = ref_day or _hoje_utc()
    metrics = get_user_metrics(user_id)
    ultimo = metrics.get("ultimo_dia_estudo")

    if not ultimo:
        dias_sem_estudar = 99
    else:
        dias_sem_estudar = max(0, (hoje - ultimo).days)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET dias_sem_estudar = %s WHERE id = %s RETURNING *", (dias_sem_estudar, user_id))
            conn.commit()
            return cur.fetchone()

def get_cached_content(user_id: str, materia: str, tema: str) -> dict[str, Any] | None:
    key = f"{user_id}:{materia.strip().lower()}:{tema.strip().lower()}"
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payload FROM content_cache WHERE cache_key = %s", (key,))
            row = cur.fetchone()
            return row["payload"] if row else None

def set_cached_content(user_id: str, materia: str, tema: str, content: dict[str, Any]) -> None:
    key = f"{user_id}:{materia.strip().lower()}:{tema.strip().lower()}"
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO content_cache (cache_key, payload)
                VALUES (%s, %s)
                ON CONFLICT (cache_key) DO UPDATE SET payload = EXCLUDED.payload
            """, (key, json.dumps(content)))
            conn.commit()

def get_ia_daily_count(user_id: str, day: date | None = None) -> int:
    metrics = get_user_metrics(user_id)
    hoje = (day or _hoje_utc()).isoformat()
    return int(metrics["ia_geracoes_por_dia"].get(hoje, 0))

def increment_ia_daily_count(user_id: str, day: date | None = None) -> int:
    metrics = get_user_metrics(user_id)
    hoje = (day or _hoje_utc()).isoformat()

    counts = metrics.get("ia_geracoes_por_dia", {})
    atual = int(counts.get(hoje, 0)) + 1
    counts[hoje] = atual

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET ia_geracoes_por_dia = %s WHERE id = %s", (json.dumps(counts), user_id))
            conn.commit()
    return atual
