import json
import os
import random
import re
import unicodedata
from datetime import datetime, timezone
import logging
import requests

from services.db import (
    get_cached_content,
    set_cached_content,
    get_cached_topic_structure,
    set_cached_topic_structure,
)
from services.lesson_reviewer import revisar_aula
from services.quality_guard import avaliar_qualidade_aula

logger = logging.getLogger(__name__)


def _titulo(txt: str) -> str:
    return txt.strip().lower().capitalize()


def limpar_unicode_invalido(obj):
    if isinstance(obj, str):
        return obj.replace("\u0000", "")
    elif isinstance(obj, list):
        return [limpar_unicode_invalido(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: limpar_unicode_invalido(v) for k, v in obj.items()}
    return obj

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
        "blocos": [
            {
                "tipo": "explicacao",
                "conteudo": (
                    f"Ops, parece que a inteligência artificial está indisponível no momento! "
                    f"Eu não consegui gerar a explicação real para '{tema}' em {materia}.\n\n"
                    f"⚠️ Motivo técnico: {erro_tecnico}"
                )
            },
            {
                "tipo": "exemplo",
                "conteudo": f"Exemplo: Quando a IA voltar, você verá um caso de uso real de {tema} aqui."
            },
            {
                "tipo": "exercicios",
                "perguntas": [
                    f"Exercício de fallback: Escreva um pequeno resumo do que você já sabe sobre {tema}.",
                    "Pressione 'Verificar e Continuar' para avançar."
                ]
            }
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
            {"role": "system", "content": "Você é um amigo extremamente inteligente e didático. Sua única função é retornar um JSON estrito."},
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
        logger.warning("Erro HTTP da OpenAI (%s): %s", response.status_code, response.text)
        return None, f"Erro HTTP {response.status_code}: {response.text}"
    except requests.exceptions.RequestException as e:
        logger.warning("Erro de conexão na IA: %s", e)
        return None, f"Erro na requisição: {e}"
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning("Erro no formato do retorno da IA: %s", e)
        return None, f"Retorno inesperado da IA: {e}"


def gerar_conteudo(materia: str, tema: str, foco_delimitado: str = "") -> dict:
    cached = get_cached_content(materia, tema, foco_delimitado)
    if cached:
        quality = avaliar_qualidade_aula(cached)
        return {**cached, "cache": True, "quality": quality, "prompt_version": "v2-mentor"}

    # A limitação drástica (FREE_DAILY_LIMIT) foi desativada durante os testes/desenvolvimento
    # para garantir que os testes massivos não ativem bloqueios artificiais silenciando a OpenAI.

    prompt = f"""Você é um Mentor de Estudo Experiente.
Sua tarefa é gerar uma aula de micro-learning focada e direta, atuando como um professor particular altamente inteligente, didático e empático, que prepara o aluno para concursos e provas difíceis.

Matéria: {materia}
Tema: {tema}
Foco Específico: {foco_delimitado}

REGRAS OBRIGATÓRIAS:
- Vá direto ao ponto. Explique o conceito de forma lógica, coesa e clara. Sem jargões exagerados de coach, mas seja encorajador.
- Use analogias APENAS se elas realmente facilitarem a compreensão do aluno de forma natural. Não force analogias do cotidiano se uma explicação matemática estruturada for mais eficiente.
- A linguagem deve ser de um amigo experiente: direto, claro e focado em resolver problemas. Use "você".
- Ensine SOMENTE o recorte solicitado em Foco Específico.
- Use formatação Markdown. Cifrões simples para matemática em linha (`$x^2$`) e duplos isolados (`$$x^2$$`). Cuidado ao usar o cifrão isolado, se for escrever o nome de uma variável ou letra, escreva em formato matemático (ex: `$a$`, `$b$`, `$c$`). PROIBIDO usar `\\[ ... \\]`, `\\( ... \\)` ou um cifrão único sem fechamento (nunca faça `a, b e $c:`).
- Gráficos Matemáticos: Se você estiver ensinando uma função matemática ou conceito que fica mais claro com um gráfico cartesiano (ex: função de 1º ou 2º grau), adicione um bloco do tipo "grafico_matematico" com a fórmula. Nosso motor backend gerará um gráfico perfeito em alta resolução para o aluno.

Formato OBRIGATÓRIO do JSON de saída (A array 'blocos' deve fluir como uma aula natural, seguido por exemplo e depois os exercicios no final):
{{
  "blocos": [
    {{
      "tipo": "explicacao",
      "conteudo": "A teoria base ensinada de forma clara."
    }},
    {{
      "tipo": "grafico_matematico",
      "funcao": "y = 2x + 1"
    }},
    {{
      "tipo": "exemplo",
      "conteudo": "Um exemplo prático passo a passo para ilustrar a teoria."
    }},
    {{
      "tipo": "exercicios",
      "lista": ["Uma pergunta curta de checagem do conceito", "Um exercício prático e direto"]
    }}
  ]
}}

REGRAS DOS EXERCÍCIOS:
- Exatamente 2 exercícios práticos, diretos e sem enrolação.
- Não incluir gabarito na pergunta.

REGRAS DE VISUAIS:
- Se precisar mostrar uma função matemática, use APENAS o bloco do tipo "grafico_matematico".
- NÃO gere código mermaid ou ascii art para tentar desenhar gráficos. Nosso sistema de backend cuida disso. Apenas passe a função puramente matemática no campo "funcao", ex: "y = x^2".

ABSOLUTAMENTE PROIBIDO:
- Não imprima pensamentos, auditoria, justificativas de bastidores ou texto fora do JSON.
- Não invente fatos técnicos sem base quando o tema exigir precisão; prefira formulação conservadora e correta.
Retorne estritamente o objeto JSON.
"""

    raw, erro_tecnico = _chamar_ia(prompt)

    # Limpa marcação Markdown se a API devolver (ex: ```json\n{...}\n```)
    if raw and raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n", "", raw)
        raw = re.sub(r"```$", "", raw).strip()

    is_fallback = False
    from services.visual_engine import processar_aula

    if raw:
        try:
            parsed = json.loads(raw)
            content = processar_aula(parsed)
            content["origem"] = "ia"
        except json.JSONDecodeError as e:
            logger.warning("Erro ao decodificar JSON gerado pela IA: %s", e)
            content = _fallback_conteudo(materia, tema, f"JSON Inválido: {e}")
            is_fallback = True
    else:
        content = _fallback_conteudo(materia, tema, erro_tecnico)
        is_fallback = True

    # IMPORTANTE: Nunca cacheie o fallback, senão o assunto ficará permanentemente inacessível mesmo após o erro resolver.
    if not is_fallback:
        content = limpar_unicode_invalido(content)
        content = revisar_aula(content)
        set_cached_content(materia, tema, foco_delimitado, content)

    quality = avaliar_qualidade_aula(content)
    if not quality["aprovado"]:
        content = revisar_aula(content)
        quality = avaliar_qualidade_aula(content)

    return {**content, "cache": False, "quality": quality, "prompt_version": "v2-mentor"}


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


def acionar_tutor_socratico(tema: str, contexto: str, pergunta: str, historico: list = None) -> str:
    historico_str = ""
    if historico:
        historico_formatado = "\n".join([f"({msg.get('role', 'unknown')}): {msg.get('text', '')}" for msg in historico[-4:]])
        historico_str = f"Histórico recente da conversa:\n{historico_formatado}\n"

    prompt = f"""Você é um Tutor Analítico e Profissional auxiliando um aluno num painel lateral durante uma aula.
Tema atual da aula: {tema}
Contexto do que o aluno estava lendo: {contexto[:3000]}

{historico_str}
Dúvida atual do aluno: {pergunta}

REGRAS:
1. Responda de forma direta, clara e objetiva. Vá direto ao ponto. Sem frases motivacionais, jargões de coach, ou elogios vazios.
2. Mantenha o contexto das mensagens anteriores se for uma continuação da dúvida.
3. Fale apenas sobre a dúvida apresentada, explicando de forma analítica e estruturada (máx 3-4 frases).
"""
    raw, erro = _chamar_ia(prompt)

    if erro:
        return "Tutor offline no momento. Tente ler a seção novamente com calma e avance."

    if raw and raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n", "", raw)
        raw = re.sub(r"```$", "", raw).strip()

    try:
        # Se a IA retornou JSON acidentalmente
        if raw.startswith("{"):
            js = json.loads(raw)
            return js.get("resposta", raw)
        return raw.strip()
    except Exception:
        return raw.strip() if raw else "Estou digerindo o conceito, pergunte novamente!"

def avaliar_resposta_exercicio(tema: str, enunciado: str, resposta_usuario: str) -> dict:
    prompt = f"""Atuando como um Mentor de Estudo avaliando uma resposta de aluno:
Tema da Aula: {tema}
Pergunta Feita: {enunciado}
Resposta do Aluno: {resposta_usuario}

Sua tarefa é ler a resposta e avaliar a intuição e raciocínio por trás dela.

REGRAS DE AVALIAÇÃO:
1. O FOCO É ENTENDIMENTO GERAL: Ignore erros de digitação. O aluno entendeu a essência? Se sim, considere correto.
2. FEEDBACK CURTO E DIRETO: Responda em no MÁXIMO 2 frases. Use tom encorajador e amigável. Se acertou, parabenize de forma simples. Se errou, mostre de forma lógica onde foi o erro para que ele tente de novo. Não force frases ou jargões de coach motivacional.
3. NUNCA DÊ A RESPOSTA PURA SE ELE ERROU: Dê uma pista ou faça uma pergunta que o ajude a chegar na conclusão correta sozinho.

Retorne ESTRITAMENTE o formato JSON a seguir:
{{
  "correto": true ou false,
  "feedback": "Feedback direto, amigável e focado em aprendizado matemático/lógico. Máx 2 frases curtas."
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
        "correto": False,
        "feedback": "A correção automática está instável agora. Releia a teoria e tente responder de novo em 1-2 frases."
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
    cached = get_cached_topic_structure(tema)
    if cached:
        return cached

    tema_norm = (tema or "").lower()
    complexidade_alta = any(k in tema_norm for k in ["exponencial", "logaritmo", "trigonom", "deriv", "integr"])
    complexidade_baixa = any(k in tema_norm for k in ["funcao afim", "primeiro grau", "porcentagem", "regra de tres"])
    if complexidade_alta:
        qtd_sugerida = 7
    elif complexidade_baixa:
        qtd_sugerida = 4
    else:
        qtd_sugerida = 5

    prompt = f"""
Sua tarefa é dividir o tema principal em subtemas estruturados para uma trilha de estudo progressiva.

Tema: {tema}

Regras ABSOLUTAS:
1. Você DEVE quebrar o tema na quantidade sugerida: {qtd_sugerida} subtemas lógicos e sequenciais.
2. Nomes descritivos: O campo "nome" deve descrever de forma clara e direta o que será estudado no bloco.
3. DIRETO AO PONTO: É ABSOLUTAMENTE PROIBIDO gerar tópicos de revisão genérica inicial.
4. O campo "foco_delimitado" DEVE guiar o conteúdo a focar em 1 ou 2 conceitos-chave, ditando rigorosamente a teoria/fórmula específica que deve ser coberta. Não obrigue o uso de analogias.

Retorne ESTRITAMENTE um objeto JSON no formato abaixo:
{{
  "subtemas": [
    {{
      "nome": "Nome do Subtema",
      "foco_delimitado": "Foco estrito do que ensinar neste bloco."
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
                subtemas = parsed["subtemas"]
                if isinstance(subtemas, list):
                    subtemas = [s for s in subtemas if isinstance(s, dict) and s.get("nome")]
                    if subtemas:
                        limite = max(3, min(8, qtd_sugerida + 1))
                        subtemas = subtemas[:limite]
                        set_cached_topic_structure(tema, subtemas)
                        return subtemas
        except json.JSONDecodeError:
            pass

    # Fallback determinístico porém variável por complexidade
    base = [
        {"nome": f"{tema} (Conceito central)", "foco_delimitado": "Definição, leitura e ideia principal."},
        {"nome": f"{tema} (Representação)", "foco_delimitado": "Como representar e interpretar no formato de prova."},
        {"nome": f"{tema} (Resolução)", "foco_delimitado": "Técnica de resolução passo a passo."},
        {"nome": f"{tema} (Questões típicas)", "foco_delimitado": "Padrões de questões mais cobrados."},
        {"nome": f"{tema} (Erros comuns)", "foco_delimitado": "Armadilhas e erros frequentes para evitar."},
        {"nome": f"{tema} (Aplicações)", "foco_delimitado": "Aplicação em situações concretas."},
        {"nome": f"{tema} (Revisão estratégica)", "foco_delimitado": "Resumo final orientado para prova."},
    ]
    fallback = base[:qtd_sugerida]
    set_cached_topic_structure(tema, fallback)
    return fallback


def recomendar_proximo_passo(taxa_acerto: float, erros_recorrentes: int) -> str:
    if taxa_acerto < 0.6:
        return "reforco"
    if erros_recorrentes >= 2:
        return "revisao-ativa"
    if taxa_acerto >= 0.85:
        return "simulado-curto"
    return "avanco-controlado"
