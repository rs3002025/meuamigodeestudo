import json
import os
from datetime import date, timedelta
from typing import Any
import logging
import re
import unicodedata

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL")
logger = logging.getLogger(__name__)


def _normalize_cache_fragment(text: str) -> str:
    raw = (text or "").strip().lower()
    raw = "".join(
        c for c in unicodedata.normalize("NFKD", raw) if not unicodedata.combining(c)
    )
    raw = re.sub(r"[^a-z0-9\s]", " ", raw)

    # Sinônimos e variações frequentes para melhorar reaproveitamento semântico
    synonyms = {
        "funcao do primeiro grau": "funcao afim",
        "funcao de primeiro grau": "funcao afim",
        "funcao 1 grau": "funcao afim",
        "equacao da reta": "funcao afim",
        "reta de 1 grau": "funcao afim",
        "intercepto": "coeficiente linear",
        "inclinacao": "coeficiente angular",
    }
    for source, target in synonyms.items():
        raw = raw.replace(source, target)

    stopwords = {"de", "do", "da", "e", "em", "para", "o", "a", "no", "na"}
    tokens = [t for t in raw.split() if t and t not in stopwords]
    tokens = sorted(set(tokens))
    return " ".join(tokens)


def _cache_key_variants(materia: str, tema: str, foco_delimitado: str = "") -> list[str]:
    m = _normalize_cache_fragment(materia)
    t = _normalize_cache_fragment(tema)
    f = _normalize_cache_fragment(foco_delimitado)

    keys = [f"{m}:{t}:{f}", f"{m}:{t}:", f"{m}:{t}:geral"]

    # fallback por matéria + raiz do tema (primeiros tokens) para captar frases diferentes do mesmo tema
    raiz = " ".join(t.split()[:3]).strip()
    if raiz:
        keys.append(f"{m}:{raiz}:")

    # Remove vazios/duplicados mantendo ordem
    out: list[str] = []
    for k in keys:
        if k and k not in out:
            out.append(k)
    return out

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
                    ia_geracoes_por_dia JSONB DEFAULT '{}'::jsonb,
                    erro_notebook JSONB DEFAULT '[]'::jsonb
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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_events (
                    id BIGSERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    event_name VARCHAR(100) NOT NULL,
                    payload JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        conn.commit()

# Initialize DB on import
try:
    init_db()
except Exception as e:
    logger.exception("Error initializing DB: %s", e)

def _hoje_utc() -> date:
    return date.today()

def get_user_metrics(user_id: str) -> dict[str, Any]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                row["ia_geracoes_por_dia"] = row["ia_geracoes_por_dia"] or {}
                row["erro_notebook"] = row.get("erro_notebook") or []
                return row

            cur.execute(
                "INSERT INTO users (id, ia_geracoes_por_dia) VALUES (%s, '{}'::jsonb) RETURNING *",
                (user_id,)
            )
            conn.commit()
            row = cur.fetchone()
            row["erro_notebook"] = row.get("erro_notebook") or []
            return row

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

def get_cached_content(materia: str, tema: str, foco_delimitado: str = "") -> dict[str, Any] | None:
    keys = _cache_key_variants(materia, tema, foco_delimitado)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM content_cache WHERE cache_key = ANY(%s) LIMIT 1",
                (keys,),
            )
            row = cur.fetchone()
            return row["payload"] if row else None

def set_cached_content(materia: str, tema: str, foco_delimitado: str, content: dict[str, Any]) -> None:
    keys = _cache_key_variants(materia, tema, foco_delimitado)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for key in keys:
                cur.execute("""
                    INSERT INTO content_cache (cache_key, payload)
                    VALUES (%s, %s::jsonb)
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
            cur.execute("UPDATE users SET ia_geracoes_por_dia = %s::jsonb WHERE id = %s", (json.dumps(counts), user_id))
            conn.commit()
    return atual


def add_error_notebook_entry(user_id: str, entry: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = get_user_metrics(user_id)
    notebook = list(metrics.get("erro_notebook") or [])
    notebook.append(entry)
    notebook = notebook[-200:]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET erro_notebook = %s::jsonb WHERE id = %s RETURNING erro_notebook",
                (json.dumps(notebook), user_id),
            )
            conn.commit()
            updated = cur.fetchone()
            return updated["erro_notebook"] if updated else notebook


def get_error_notebook(user_id: str) -> list[dict[str, Any]]:
    metrics = get_user_metrics(user_id)
    return list(metrics.get("erro_notebook") or [])


def log_telemetry(user_id: str | None, event_name: str, payload: dict[str, Any] | None = None) -> None:
    event_payload = payload or {}
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO telemetry_events (user_id, event_name, payload)
                    VALUES (%s, %s, %s::jsonb)
                    """,
                    (user_id, event_name, json.dumps(event_payload)),
                )
                conn.commit()
    except Exception as exc:
        logger.warning("Falha ao registrar telemetria: %s", exc)
