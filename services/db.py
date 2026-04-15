import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryDB:
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    plans: dict[str, dict[str, Any]] = field(default_factory=dict)
    tasks: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)


memory = MemoryDB()
has_database_url = bool(os.getenv("DATABASE_URL"))


def db_unavailable_error() -> RuntimeError:
    return RuntimeError(
        "DATABASE_URL não configurada. Use o armazenamento em memória para desenvolvimento local."
    )
