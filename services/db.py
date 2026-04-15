import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any


@dataclass
class MemoryDB:
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    plans: dict[str, dict[str, Any]] = field(default_factory=dict)
    tasks: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, dict[str, Any]] = field(default_factory=dict)


memory = MemoryDB()
has_database_url = bool(os.getenv("DATABASE_URL"))


def db_unavailable_error() -> RuntimeError:
    return RuntimeError(
        "DATABASE_URL não configurada. Use o armazenamento em memória para desenvolvimento local."
    )


def _hoje_utc() -> date:
    return date.today()


def _to_date(raw: str | None) -> date | None:
    if not raw:
        return None
    return date.fromisoformat(raw)


def get_user_metrics(user_id: str) -> dict[str, Any]:
    if user_id not in memory.metrics:
        memory.metrics[user_id] = {
            "dias_consecutivos": 0,
            "ultimo_dia_estudo": None,
            "ultima_taxa_acerto": None,
            "dias_sem_estudar": 0,
            "conteudos_recentes_avaliacao": [],
        }
    return memory.metrics[user_id]


def registrar_estudo(user_id: str, studied_on: date | None = None) -> dict[str, Any]:
    hoje = studied_on or _hoje_utc()
    metrics = get_user_metrics(user_id)

    ultimo = _to_date(metrics.get("ultimo_dia_estudo"))
    if ultimo == hoje:
        metrics["dias_sem_estudar"] = 0
        return metrics

    if ultimo == (hoje - timedelta(days=1)):
        metrics["dias_consecutivos"] += 1
    else:
        metrics["dias_consecutivos"] = 1

    metrics["ultimo_dia_estudo"] = hoje.isoformat()
    metrics["dias_sem_estudar"] = 0
    return metrics


def atualizar_dias_sem_estudar(user_id: str, ref_day: date | None = None) -> dict[str, Any]:
    hoje = ref_day or _hoje_utc()
    metrics = get_user_metrics(user_id)
    ultimo = _to_date(metrics.get("ultimo_dia_estudo"))

    if not ultimo:
        metrics["dias_sem_estudar"] = 99
        return metrics

    diff = (hoje - ultimo).days
    metrics["dias_sem_estudar"] = max(0, diff)
    return metrics
