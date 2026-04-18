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


def gerar_conteudo(user_id: str, materia: str, tema: str, foco_delimitado: str = "") -> dict:
    cached = get_cached_content(user_id, materia, tema)
    if cached:
        return {**cached, "cache": True}

    # A limitação drástica (FREE_DAILY_LIMIT) foi desativada durante os testes/desenvolvimento
    # para garantir que os testes massivos não ativem bloqueios artificiais silenciando a OpenAI.

    prompt = f"""Você é um professor particular ensinando de forma clara e direta.

Matéria: {materia}
Tema: {tema}
Foco Específico da Aula: {foco_delimitado}

REGRA PRINCIPAL:
- Ensine SOMENTE o tema informado e restrito ao "Foco Específico da Aula".
- NÃO explique conceitos mais básicos
- NÃO amplie o assunto, não ensine os passos seguintes

Estrutura obrigatória:
1) Explicação direta do tema
2) Como funciona
3) Exemplo
4) 2 ou 3 exercícios

Regras de Formatação (MUITO IMPORTANTE):
- Use Markdown rico.
- Faça parágrafos curtos e pule linhas entre eles.
- Use cabeçalhos (###), negrito (**texto**) e bullet points para não gerar blocos maciços e confusos de texto.

Regras Didáticas:
- linguagem simples
- sem linguagem acadêmica
- sem fugir do tema
- não ser superficial
- não ser excessivamente longo
- não dar resposta dos exercícios (NUNCA coloque a resposta ou dicas da resposta entre parênteses)

Retorne ESTRITAMENTE em JSON:
{{
  "explicacao": "Sua explicação detalhada, linda e muito bem formatada em Markdown, juntamente com 'como funciona'. Use quebras de linha e emojis.",
  "exemplo": "Um exemplo claro e aplicável, formatado em Markdown.",
  "exercicios": ["...", "..."]
}}
"""

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
                "referencias": parsed.get("referencias") or "### 🔎 Referências Recomendadas\n- *Mentor*: A IA não pôde carregar as referências no momento.",
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
    prompt = f"""Atuando como um professor avaliando a resposta de um aluno:
Tema da Aula: {tema}
Pergunta Feita: {enunciado}
Resposta do Aluno: {resposta_usuario}

Sua tarefa é ler a resposta e avaliar se demonstra compreensão.
IMPORTANTE: Use o tom de "parceiro de estudos", falando diretamente com o aluno em SEGUNDA PESSOA (você). NUNCA fale em terceira pessoa (ex: "o aluno acertou").
Diga algo como: "Muito bem, você pegou a ideia!" ou "Você quase lá, mas lembre-se que...".

Retorne ESTRITAMENTE o formato JSON a seguir:
{{
  "correto": true ou false (boolean),
  "feedback": "Um parágrafo curto (1 ou 2 frases) explicando por que VOCÊ acertou ou como VOCÊ poderia melhorar caso tenha errado. Seja direto, íntimo e muito encorajador."
}}"""

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


def gerar_estrutura_tema(tema: str) -> list[dict]:
    prompt = f"""
Sua tarefa é analisar o tema principal abaixo e deduzir TUDO o que é necessário para aprender esse conteúdo de forma completa e lógica.
Depois, monte um plano de estudos dividindo esse conteúdo em subtemas estruturados.

Tema: {tema}

Regras:
1. Analise o que é preciso para aprender todo o conteúdo necessário.
2. Divida o tema em subtemas ordenados (máximo de 5 a 6 itens).
3. A progressão deve ser altamente inteligente e lógica (do básico necessário até a aplicação).
4. Para que os conteúdos não se repitam depois, você DEVE definir exatamente qual é o "foco" de cada subtema.

Retorne ESTRITAMENTE um objeto JSON no formato abaixo:
{{
  "subtemas": [
    {{
      "nome": "O nome curto e direto do subtema",
      "foco_delimitado": "A instrução estrita do que deve ser ensinado apenas aqui, para não atropelar ou se misturar com os próximos."
    }}
  ]
}}
""".strip()

    raw, _ = _chamar_ia(prompt)
    if raw and raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n", "", raw)
        raw = re.sub(r"```$", "", raw).strip()

    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and "subtemas" in parsed:
                return parsed["subtemas"]
        except json.JSONDecodeError:
            pass

    # Fallback determinístico caso a IA falhe
    return [
        {
            "nome": f"{tema} (Fundamentos)",
            "foco_delimitado": "Apenas conceitos introdutórios e definições básicas."
        },
        {
            "nome": f"{tema} (Aprofundamento)",
            "foco_delimitado": "Foco em regras mais avançadas, fórmulas ou estruturas complexas."
        },
        {
            "nome": f"{tema} (Aplicações)",
            "foco_delimitado": "Exclusivo para casos de uso e exemplos práticos reais do dia a dia."
        }
    ]
