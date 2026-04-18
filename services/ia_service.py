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

    prompt = f"""Atue como um Mestre Didático: um professor particular brilhante, incrivelmente didático e que domina a arte de ensinar.

Matéria: {materia}
Tema: {tema}
Foco Específico da Aula: {foco_delimitado}

REGRA PRINCIPAL:
- Ensine SOMENTE o tema informado e restrito ao "Foco Específico da Aula".
- NÃO amplie o assunto, não ensine os passos seguintes, mantenha-se estritamente no escopo da aula.

Estrutura obrigatória:
1) Explicação da teoria
2) Como funciona na prática
3) Exemplos resolvidos PASSO A PASSO
4) Controle de Qualidade: Antes de finalizar a explicação, você deve agir como auditor e ter certeza de que ensinou de forma que uma pessoa com dificuldade entenderia 100%, sem ser vago ou incompleto.

Regras de Formatação (MUITO IMPORTANTE):
- Use Markdown rico (cabeçalhos, negrito, itálico, listas, emojis).
- Quebre muito bem os parágrafos. NÃO construa blocos gigantes e maciços de texto.
- Crie um visual agradável para leitura em celular.

Regras Didáticas:
- Linguagem absurdamente simples, acessível e natural.
- SEM jargões acadêmicos complicados.
- PROFUNDIDADE SEM COMPLEXIDADE: Fale simples, mas não seja vago. Cubra o conteúdo necessário com maestria.
- Durante a explicação (no JSON de 'explicacao'), insira pequenos exemplos práticos e resolvidos passo a passo para ilustrar a teoria enquanto você ensina.

Exercícios (Regras):
- Formule 2 ou 3 exercícios criativos.
- VARIE OS FORMATOS: Crie um exercício de múltipla escolha (sem mostrar o gabarito), outro aberto, e outro como desafio prático ou de verdadeiro/falso.
- NUNCA dê as respostas ou dicas das respostas no enunciado.

Retorne ESTRITAMENTE em JSON:
{{
  "explicacao": "A explicação completa, amigável, profunda (mas simples), bem espaçada e com exemplos passo a passo.",
  "exemplo": "Um grande exemplo real aplicado ou analogia final que sela o conhecimento.",
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

REGRAS DE AVALIAÇÃO:
1. SEJA MUITO FLEXÍVEL: Ignore completamente erros de digitação, falta de acentuação ou respostas muito curtas/informais, desde que a ideia central ou a intuição do aluno esteja minimamente correta.
2. SÓ MARQUE COMO ERRADO (false): Se o aluno escrever algo completamente fora do contexto, assumir um conceito gravemente errado, ou disser "não sei".
3. TOM E EMPATIA: Fale diretamente com o aluno em SEGUNDA PESSOA ("você"). Seja absurdamente amigável, acolhedor e encorajador. Jamais use um tom robótico ou punitivo. Se ele acertar a ideia, elogie com entusiasmo. Se errar, seja gentil e explique rapidamente o ponto principal sem fazer ele se sentir mal.

Retorne ESTRITAMENTE o formato JSON a seguir:
{{
  "correto": true ou false,
  "feedback": "Seu feedback super amigável e conversacional, focando em incentivar e corrigir a direção (1 ou 2 frases no máximo)."
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
4. IMPORTANTE: No campo "nome", forneça APENAS o nome específico do subtema (ex: "Coordenadas e Proporcionalidade" ou "Gráficos"). NÃO REPETIR o nome do tema original junto (não faça "Função afim - Gráficos").
5. Para que os conteúdos não se repitam depois, você DEVE definir exatamente qual é o "foco_delimitado" de cada subtema.

Retorne ESTRITAMENTE um objeto JSON no formato abaixo:
{{
  "subtemas": [
    {{
      "nome": "Apenas o nome próprio e curto do subtema",
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
