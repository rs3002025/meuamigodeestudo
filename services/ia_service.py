import json
import os
import random
import re
import unicodedata
from datetime import datetime, timezone
import requests

from services.db import (
    get_cached_content,
    increment_ia_daily_count,
    set_cached_content,
)


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


def _fallback_conteudo(materia: str, tema: str, erro_tecnico: str = None) -> dict:
    if not erro_tecnico:
        erro_tecnico = "O administrador não configurou a chave da API." if not os.getenv("OPENAI_API_KEY") else "Houve uma falha de conexão ou parsing temporária."

    return {
        "explicacao": (
            f"Ops, parece que a inteligência artificial está indisponível no momento! "
            f"Eu não consegui gerar a explicação real para '{tema}' em {materia}.\n\n"
            f"⚠️ Motivo técnico: {erro_tecnico}"
        ),
        "exemplo": f"Exemplo: Quando a IA voltar, você verá um caso de uso real de {tema} aqui.",
        "exercicios": [
            f"Exercício de fallback: Escreva um pequeno resumo do que você já sabe sobre {tema}.",
            "Pressione 'Verificar e Continuar' para avançar.",
        ],
        "origem": "fallback-local",
    }


def _chamar_ia(prompt: str) -> tuple[str | None, str | None]:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        api_key = api_key.strip()

    if not api_key:
        return None, "Variável de ambiente OPENAI_API_KEY ausente ou vazia."

    payload = {
        "model": "gpt-5.4-nano",
        "messages": [
            {"role": "system", "content": "Você é um professor particular experiente. Sua única função é retornar um JSON estrito."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"], None
    except requests.exceptions.HTTPError as e:
        print(f"Erro HTTP da OpenAI ({response.status_code}): {response.text}")
        return None, f"Erro HTTP {response.status_code}: {response.text}"
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão na IA: {e}")
        return None, f"Erro na requisição: {e}"
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"Erro no formato do retorno da IA: {e}")
        return None, f"Retorno inesperado da IA: {e}"


def gerar_conteudo(user_id: str, materia: str, tema: str) -> dict:
    cached = get_cached_content(user_id, materia, tema)
    if cached:
        return {**cached, "cache": True}

    # A limitação drástica (FREE_DAILY_LIMIT) foi desativada durante os testes/desenvolvimento
    # para garantir que os testes massivos não ativem bloqueios artificiais silenciando a OpenAI.

    prompt = f"""
Você é um professor particular focado em Micro-learning (ensino em pílulas).
Ensine o seguinte tópico para um aluno que está estudando sozinho.
Materia: {materia}
Tema: {tema}

Retorne estritamente um JSON com a exata estrutura e regras abaixo:
{{
  "explicacao": "Um texto EXTREMAMENTE visual e agradável de ler. Use quebras de linha (\\n), emojis e bullet points. Introduza o tema e liste 3 fatos importantes de forma pontual e didática.",
  "exemplo": "Uma analogia incrível e divertida com a vida real (ex: compras, cotidiano, jogos) para fixar o conceito, separada em pequenos parágrafos.",
  "exercicios": [
    "Uma pergunta que faça o aluno pensar e digitar a resposta com as próprias palavras.",
    "Uma situação-problema onde ele precise aplicar a teoria ensinada."
  ]
}}
""".strip()

    raw, erro_tecnico = _chamar_ia(prompt)

    # Limpa marcação Markdown se a API devolver (ex: ```json\n{...}\n```)
    if raw and raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n", "", raw)
        raw = re.sub(r"```$", "", raw).strip()

    is_fallback = False
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
            content = _fallback_conteudo(materia, tema, f"JSON Inválido: {e}")
            is_fallback = True
    else:
        content = _fallback_conteudo(materia, tema, erro_tecnico)
        is_fallback = True

    increment_ia_daily_count(user_id)

    # IMPORTANTE: Nunca cacheie o fallback, senão o assunto ficará permanentemente inacessível mesmo após o erro resolver.
    if not is_fallback:
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


def avaliar_resposta_exercicio(tema: str, enunciado: str, resposta_usuario: str) -> dict:
    prompt = f"""
Atuando como um professor avaliando a resposta de um aluno:
Tema da Aula: {tema}
Pergunta Feita: {enunciado}
Resposta do Aluno: {resposta_usuario}

Sua tarefa é ler a resposta do aluno e avaliá-corretamente se ela demonstra compreensão do conceito. Mesmo que seja informal, se a lógica estiver correta, considere aprovado.
Retorne ESTRITAMENTE o formato JSON a seguir:
{{
  "correto": true ou false (boolean),
  "feedback": "Um parágrafo curto (até 2 frases) explicando por que a resposta do aluno está certa ou como ele poderia melhorar caso tenha errado. Seja muito encorajador e amigável."
}}
""".strip()

    raw, _ = _chamar_ia(prompt)

    if raw and raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n", "", raw)
        raw = re.sub(r"```$", "", raw).strip()

    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    # Fallback no caso da IA falhar na correção
    return {
        "correto": True,
        "feedback": "Tudo certo! Continue focado e vamos em frente."
    }

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
