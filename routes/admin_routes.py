import logging
import os

from flask import Blueprint, jsonify, request

from services.db import get_db_connection

admin_bp = Blueprint("admin", __name__)
logger = logging.getLogger(__name__)

TABLES_TO_CLEAR = ["tasks", "plans", "users", "content_cache"]


def _require_admin_key():
    """Returns an error response tuple if the request is not authorised, else None."""
    admin_key = os.getenv("ADMIN_API_KEY", "").strip()
    if not admin_key:
        return jsonify({"erro": "ADMIN_API_KEY não configurada no servidor."}), 503

    provided = request.headers.get("X-Admin-Key", "").strip()
    if not provided or provided != admin_key:
        return jsonify({"erro": "Não autorizado. Forneça a chave correta no header X-Admin-Key."}), 401

    return None


@admin_bp.post("/clear-tables")
def clear_tables():
    """
    Truncates the tables: tasks, plans, users, content_cache (in that order).
    Requires the X-Admin-Key header to match the ADMIN_API_KEY environment variable.
    """
    auth_error = _require_admin_key()
    if auth_error:
        return auth_error

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for table in TABLES_TO_CLEAR:
                    cur.execute(f"TRUNCATE TABLE {table} CASCADE")
            conn.commit()

        logger.warning("Admin clear-tables executado. Tabelas limpas: %s", TABLES_TO_CLEAR)
        return jsonify({
            "ok": True,
            "mensagem": "Tabelas limpas com sucesso.",
            "tabelas": TABLES_TO_CLEAR,
        }), 200

    except Exception as exc:
        logger.exception("Erro ao limpar tabelas: %s", exc)
        return jsonify({"erro": "Falha ao limpar tabelas.", "detalhe": str(exc)}), 500
