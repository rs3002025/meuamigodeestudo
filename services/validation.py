from typing import Any


def parse_float(value: Any, default: float = 0.0) -> tuple[float | None, str | None]:
    if value is None:
        return default, None
    try:
        return float(value), None
    except (TypeError, ValueError):
        return None, "valor numérico inválido"


def parse_int(value: Any, default: int = 0) -> tuple[int | None, str | None]:
    if value is None:
        return default, None
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, "valor inteiro inválido"
