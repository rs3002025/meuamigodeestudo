import json
import os
import random
import re
import unicodedata
from datetime import datetime, timezone
from urllib import error, request

from services.db import (
    get_cached_content,
    get_ia_daily_count,
    increment_ia_daily_count,
    set_cached_content,
)

FREE_DAILY_LIMIT = 3


def _titulo(txt: str) -> str:
    return txt.strip().lower().capitalize()


def normalizar_lista_conteudos(raw: str) -> list[str]:
    cleaned = (raw or "").replace(";", ",")
    if "," in cleaned:
        chunks = [p.strip() for p in cleaned.split(",") if p.strip()]
    else:
        tokens = [p.strip() for p in re.split(r"\s+", cleaned) if p.strip()]
        chunks = []
        current = []
        for token in tokens:
            current.append(token)
            if len(current) == 2:
                chunks.append(" ".join(current))
                current = []
        if current:
            chunks.append(" ".join(current))

    alias = {
        "portugues": "Português",
        "matematica": "Matemática",
        "matematica basica": "Matemática básica",
        "raciocinio": "Raciocínio lógico",
        "raciocinio logico": "Raciocínio lógico",
    }

    normalized: list[str] = []
    for item in chunks:
        item_low = item.lower().strip()
        ascii_item = "".join(
            c for c in unicodedata.normalize("NFKD", item_low) if not unicodedata.combining(c)
        )
        normalized_item = alias.get(ascii_item, _titulo(item_low))
        if normalized_item and normalized_item not in normalized:
            normalized.append(normalized_item)
    return normalized


def _fallback_conteudo(materia: str, tema: str) -> dict:
    return {
        "explicacao": (
            f"{tema} em {materia}: ideia central em linguagem simples. "
            "Lê com calma e conecta com um exemplo do dia a dia."
        ),
        "exemplo": f"Exemplo rápido: aplique {tema} para resolver um problema básico de {materia}.",
        "exercicios": [
            f"Explique com suas palavras o conceito principal de {tema}.",
            f"Resolva 1 questão curta sobre {tema} e confira o raciocínio.",
        ],
        "origem": "fallback-local",
    }


def _chamar_ia(prompt: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    payload = {
        "model": "gpt-4.1-mini",
        "input": prompt,
    }

    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("output_text")
    except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None


def gerar_conteudo(user_id: str, materia: str, tema: str) -> dict:
    cached = get_cached_content(user_id, materia, tema)
    if cached:
        return {**cached, "cache": True}

    if get_ia_daily_count(user_id) >= FREE_DAILY_LIMIT:
        fallback = {
            **_fallback_conteudo(materia, tema),
            "aviso": "limite diário do plano free atingido (3 conteúdos).",
        }
        set_cached_content(user_id, materia, tema, fallback)
        return {**fallback, "cache": False}

    prompt = f"""
Explique de forma simples:

Tema: {tema} ({materia})

Regras:
- até 5 linhas
- linguagem simples
- incluir exemplo
- incluir 2 exercícios
- responder em JSON com chaves: explicacao, exemplo, exercicios
""".strip()

    raw = _chamar_ia(prompt)
    if raw:
        try:
            parsed = json.loads(raw)
            content = {
                "explicacao": parsed.get("explicacao") or _fallback_conteudo(materia, tema)["explicacao"],
                "exemplo": parsed.get("exemplo") or _fallback_conteudo(materia, tema)["exemplo"],
                "exercicios": parsed.get("exercicios") or _fallback_conteudo(materia, tema)["exercicios"],
                "origem": "ia",
            }
        except json.JSONDecodeError:
            content = _fallback_conteudo(materia, tema)
    else:
        content = _fallback_conteudo(materia, tema)

    increment_ia_daily_count(user_id)
    set_cached_content(user_id, materia, tema, content)
    return {**content, "cache": False}


def gerar_questoes(tema: str = "tema geral", quantidade: int = 3) -> list[dict]:
    stamp = int(datetime.now(timezone.utc).timestamp())
    return [
        {
            "id": f"q-{stamp}-{i + 1}",
            "tema": tema,
            "enunciado": f"Questão {i + 1}: conceito central de {tema} em 2 linhas.",
            "tipo": "aberta",
        }
        for i in range(quantidade)
    ]


def classificar_erro(resposta_correta: str, resposta_usuario: str) -> str:
    if not resposta_usuario or len(resposta_usuario.strip()) < 4:
        return "distracao"

    palavras = [p for p in resposta_correta.lower().split(" ") if len(p) > 4]
    acertou = any(palavra in resposta_usuario.lower() for palavra in palavras)
    return "interpretacao" if acertou else "conteudo"


def gerar_avaliacao_invisivel(objetivo: str | list[str], conteudos_recentes: list[str] | None = None) -> dict:
    temas = objetivo if isinstance(objetivo, list) else [objetivo]
    recentes = set(conteudos_recentes or [])
    candidatos = [t for t in temas if t and t not in recentes]
    tema = candidatos[0] if candidatos else (temas[0] if temas[0] else "revisao geral")

    return {
        "surpresa": True,
        "questoes": gerar_questoes(tema, 2),
    }


def talvez_gerar_avaliacao_invisivel(
    objetivo: str | list[str],
    conteudos_recentes: list[str] | None = None,
    chance: float = 0.2,
) -> dict | None:
    if random.random() < chance:
        return gerar_avaliacao_invisivel(objetivo, conteudos_recentes)
    return None
