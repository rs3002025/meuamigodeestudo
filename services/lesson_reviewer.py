from __future__ import annotations

from copy import deepcopy
from typing import Any


def revisar_aula(content: dict[str, Any]) -> dict[str, Any]:
    revisado = deepcopy(content)
    blocos = revisado.get("blocos") or []

    for bloco in blocos:
        if bloco.get("tipo") == "explicacao":
            txt = (bloco.get("conteudo") or "").strip()
            if txt and "Resumo rápido" not in txt:
                bloco["conteudo"] = (
                    "### Resumo rápido\n"
                    "- Foque no núcleo da ideia antes de decorar fórmula.\n"
                    "- Resolva uma questão por etapa (identificar → montar → calcular).\n\n"
                    f"{txt}"
                )

    revisado["blocos"] = blocos
    return revisado
