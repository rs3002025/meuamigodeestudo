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


def gerar_mensagem_amigo(tema: str) -> str:
    mensagens = [
        f"isso aqui em {tema} cai direto em prova, presta atenção nisso",
        f"se tu entender essa parte de {tema}, já resolve muita questão",
        f"essa parte de {tema} é onde a maioria erra",
        f"isso aqui é chave pra prova, foca nisso"
    ]
    return random.choice(mensagens)

def gerar_conteudo(materia: str, tema: str, foco_delimitado: str = "") -> dict:
    cached = get_cached_content(materia, tema, foco_delimitado)
    if cached:
        # Prependa a mensagem amigável no início da explicação para não quebrar o frontend
        mensagem = gerar_mensagem_amigo(tema)
        blocos = cached.get("blocos", [])
        if blocos and blocos[0].get("tipo") == "explicacao":
            conteudo_atual = blocos[0].get("conteudo", "")
            if f"**{mensagem}**" not in conteudo_atual:
                blocos[0]["conteudo"] = f"**{mensagem}**\n\n{conteudo_atual}"
        return {**cached, "cache": True}

    # A limitação drástica (FREE_DAILY_LIMIT) foi desativada durante os testes/desenvolvimento
    # para garantir que os testes massivos não ativem bloqueios artificiais silenciando a OpenAI.

    prompt = f"""Você é um sistema de ensino inteligente, atuando como um amigo extremamente didático que explica de forma simples e direta.
Gere uma aula estruturada, dividida em blocos sequenciais.

Matéria: {materia}
Tema: {tema}
Foco Específico: {foco_delimitado}

REGRAS OBRIGATÓRIAS:
- Ensine SOMENTE esse recorte
- Não fuja do tema ou ensine conceitos não solicitados
- Linguagem simples, conversacional e direta (use a segunda pessoa "você")
- Nível de prova: a explicação deve ser suficiente para o aluno resolver questões sobre o tema.
- Use formatação Markdown. Cifrões simples para matemática em linha (`$x^2$`) e duplos isolados (`$$x^2$$`). PROIBIDO usar `\\[ ... \\]` ou `\\( ... \\)`.

Formato OBRIGATÓRIO do JSON de saída:
{{
  "blocos": [
    {{
      "tipo": "explicacao",
      "conteudo": "A explicação direta e didática, como se falasse com um amigo, quebrada em parágrafos."
    }},
    {{
      "tipo": "visual",
      "visual": {{
        "tipo": "grafico | tabela | diagrama | nenhum",
        "descricao": "O que este visual representa e por que ajuda",
        "funcao": "y = x^2 - 4x + 3",
        "dados": {{
          "x": [-2, -1, 0, 1, 2],
          "y": [4, 1, 0, 1, 4],
          "labels": ["Conceito", "Definição"],
          "valores": [["Sujeito", "Quem pratica"]]
        }}
      }}
    }},
    {{
      "tipo": "exemplo",
      "conteudo": "Um exemplo prático e resolvido passo a passo ilustrando a teoria."
    }},
    {{
      "tipo": "exercicios",
      "lista": ["Enunciado da questão 1", "Enunciado da questão 2"]
    }}
  ]
}}

REGRAS DE VISUAIS:
- Se precisar mostrar uma função matemática (parábola, reta, etc), passe a equação matemática real no campo "funcao" (ex: "y = x^2"). O nosso motor criará os dados e gráficos reais interativos.
- Para outros gráficos/tabelas preencha o campo "dados".
- NÃO gere HTML, não gere Markdown de imagens, nem links Pollinations. Apenas JSON estruturado puro.

ABSOLUTAMENTE PROIBIDO: Não imprima seus pensamentos ou "auditoria" no JSON de saída. Retorne estritamente o objeto JSON.
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
        set_cached_content(materia, tema, foco_delimitado, content)

    mensagem = gerar_mensagem_amigo(tema)

    # Injeta a mensagem no primeiro bloco de explicacao ou adiciona no topo
    blocos = content.get("blocos", [])
    if blocos and blocos[0].get("tipo") == "explicacao":
        explicacao_atual = blocos[0].get("conteudo", "")
        blocos[0]["conteudo"] = f"**{mensagem}**\n\n{explicacao_atual}"
    else:
        blocos.insert(0, {"tipo": "explicacao", "conteudo": f"**{mensagem}**"})

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
    prompt = f"""Atuando como um parceiro de estudos ajudando a revisar o que foi aprendido:
Tema da Aula: {tema}
Pergunta Feita: {enunciado}
Resposta do Aluno: {resposta_usuario}

Sua tarefa é ler a resposta e avaliar se demonstra compreensão.

REGRAS DE AVALIAÇÃO:
1. SEJA MUITO FLEXÍVEL: Ignore completamente erros de digitação, falta de acentuação ou respostas muito curtas/informais, desde que a ideia central ou a intuição esteja minimamente correta.
2. SÓ MARQUE COMO ERRADO (false): Se a resposta for completamente fora do contexto, assumir um conceito gravemente errado, ou disser "não sei".
3. TOM DE AMIGO: Fale diretamente com a pessoa em SEGUNDA PESSOA ("você" ou "tu"). Aja como um amigo que está ajudando a estudar. Seja encorajador e descontraído. Se acertar a ideia, elogie de forma natural. Se errar, seja compreensivo e explique rapidamente o ponto principal de forma simples, sem parecer um professor dando bronca ou sendo formal.

Retorne ESTRITAMENTE o formato JSON a seguir:
{{
  "correto": true ou false,
  "feedback": "Seu feedback super amigável, direto e conversacional, focando em incentivar ou corrigir a direção (1 ou 2 frases no máximo)."
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
Sua tarefa é dividir o tema principal em subtemas.

Tema: {tema}

Regras ABSOLUTAS:
1. Você DEVE quebrar o tema em uma quantidade adequada à complexidade.
   Quantidade sugerida para este tema: {qtd_sugerida} subtemas.
2. Seja EXTREMAMENTE conciso. Divida apenas o conteúdo principal e a progressão deve preparar para prova.
3. DIRETO AO PONTO: Assuma que o aluno já tem a base. É ABSOLUTAMENTE PROIBIDO gerar tópicos de revisão inicial genérica (Ex: se o tema for Equação Quadrática, não ensine plano cartesiano). Comece direto no assunto da Equação Quadrática.
4. NÍVEL DE ENSINO MÉDIO: NÃO gere tópicos de aprofundamento acadêmico além do necessário. A progressão deve focar estritamente em resolver a prova.
5. A progressão deve ser ágil e lógica.
6. IMPORTANTE: No campo "nome", forneça APENAS o nome específico do subtema curto e claro.
7. O campo "foco_delimitado" serve para restringir a IA que vai gerar o conteúdo do subtema.

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
