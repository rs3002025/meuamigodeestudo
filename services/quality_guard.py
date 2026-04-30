from __future__ import annotations

from typing import Any


def avaliar_qualidade_aula(content: dict[str, Any]) -> dict[str, Any]:
    blocos = content.get("blocos") or []
    score = 100
    alertas: list[str] = []

    tipos = [b.get("tipo") for b in blocos if isinstance(b, dict)]
    if "explicacao" not in tipos:
        score -= 40
        alertas.append("Aula sem bloco de explicação.")
    if "exemplo" not in tipos:
        score -= 20
        alertas.append("Aula sem exemplo prático.")
    if "exercicios" not in tipos and "exercicio" not in tipos:
        score -= 25
        alertas.append("Aula sem exercícios.")

    explicacao = next((b for b in blocos if b.get("tipo") == "explicacao"), {})
    texto = (explicacao.get("conteudo") or "").lower()

    # Relaxando o validador para aceitar a nova estrutura socrática que não tem mais os titulos chatos "o que é".
    if "analogia" not in texto and "imagine" not in texto and "pense" not in texto:
        score -= 10
        alertas.append("Falta a Analogia Elite ou uma âncora imaginativa forte.")

    ex_bloco = next((b for b in blocos if b.get("tipo") in {"exercicios", "exercicio"}), {})
    lista = ex_bloco.get("lista") or ex_bloco.get("perguntas") or []
    if len(lista) < 2:
        score -= 10
        alertas.append("Quantidade de exercícios abaixo do mínimo recomendado (2).")

    score = max(0, min(100, score))
    return {"score": score, "alertas": alertas, "aprovado": score >= 70}
