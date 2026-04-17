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
    api_key_status = "O administrador do sistema não configurou a chave da API (OPENAI_API_KEY) no ambiente." if not os.getenv("OPENAI_API_KEY") else "Houve uma falha de conexão temporária."
    return {
        "explicacao": (
            f"Ops, parece que a inteligência artificial está indisponível no momento! "
            f"Eu não consegui gerar a explicação real para '{tema}' em {materia}.\n\n"
            f"⚠️ Motivo técnico: {api_key_status}"
        ),
        "exemplo": f"Exemplo: Quando a IA voltar, você verá um caso de uso real de {tema} aqui.",
        "exercicios": [
            f"Exercício de fallback: Escreva um pequeno resumo do que você já sabe sobre {tema}.",
            "Pressione 'Verificar e Continuar' para avançar.",
        ],
        "origem": "fallback-local",
    }


def _chamar_ia(prompt: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return None

    payload = {
        "model": "gpt-5.4-nano",
        "messages": [
            {"role": "system", "content": "Você é um professor particular experiente. Sua única função é retornar um JSON estrito."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"}
    }

    req = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        # Increase timeout to 60s as some complex requests might delay
        with request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"Erro HTTP da OpenAI ({e.code}): {error_body}")
        return None
    except (error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"Erro de conexão/parse na IA: {e}")
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
Explique de forma simples e direta o seguinte tópico para um aluno estudando sozinho.
Materia: {materia}
Tema: {tema}

Retorne estritamente um JSON com a exata estrutura:
{{
  "explicacao": "O conceito principal com linguagem simples em até 2 parágrafos pequenos.",
  "exemplo": "Um exemplo prático e de fácil entendimento.",
  "exercicios": [
    "Pergunta reflexiva ou prática número 1.",
    "Pergunta reflexiva ou prática número 2."
  ]
}}
""".strip()

    raw = _chamar_ia(prompt)

    # Limpa marcação Markdown se a API devolver (ex: ```json\n{...}\n```)
    if raw and raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n", "", raw)
        raw = re.sub(r"```$", "", raw).strip()

    if raw:
        try:
            parsed = json.loads(raw)
            content = {
                "explicacao": parsed.get("explicacao") or _fallback_conteudo(materia, tema)["explicacao"],
                "exemplo": parsed.get("exemplo") or _fallback_conteudo(materia, tema)["exemplo"],
                "exercicios": parsed.get("exercicios") or _fallback_conteudo(materia, tema)["exercicios"],
                "origem": "ia",
            }
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON gerado pela IA. Retorno cru: {raw} | Erro: {e}")
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
