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


def gerar_mensagem_amigo(tema: str) -> str:
    mensagens = [
        f"Alerta tático: {tema} é o divisor de águas entre o amador e a elite. Absorva isso.",
        f"Estratégia pura: Quem domina {tema} não perde tempo em prova. Foca no fundamento.",
        f"Essa é a armadilha onde 90% cai. Se entender {tema} hoje, você já passou eles.",
        f"Missão crítica: A lógica por trás de {tema} vai desbloquear os próximos 5 assuntos."
    ]
    return random.choice(mensagens)


def _extrair_funcoes_para_visuais(texto: str) -> list[str]:
    if not texto:
        return []
    candidatos = re.findall(r"y\s*=\s*[^\n,;]+", texto, flags=re.IGNORECASE)
    validos: list[str] = []
    for c in candidatos:
        fn = c.strip().replace("**", "^")
        fn = re.sub(r"[^0-9a-zA-Z\s\^\*\+\-\/=().,]", "", fn)
        fn = re.sub(r"\s+(para|onde|com|pois|porque)\b.*$", "", fn, flags=re.IGNORECASE)
        fn = fn.strip()
        if len(fn) <= 80 and any(ch in fn.lower() for ch in ["x", "sin", "cos", "tan", "log", "exp"]):
            if fn not in validos:
                validos.append(fn)
    return validos[:2]


def _injetar_visuais_automaticos(content: dict, tema: str) -> dict:
    blocos = content.get("blocos", [])
    if not blocos:
        return content

    textos_base = []
    for bloco in blocos:
        if bloco.get("tipo") in {"explicacao", "exemplo"}:
            textos_base.append(bloco.get("conteudo", ""))

    funcoes: list[str] = []
    funcoes_existentes: set[str] = set()
    for bloco in blocos:
        if bloco.get("tipo") == "visual":
            visual = bloco.get("visual") or {}
            fn = (visual.get("funcao") or "").strip().lower()
            if fn:
                funcoes_existentes.add(fn)
    for txt in textos_base:
        for fn in _extrair_funcoes_para_visuais(txt):
            if fn not in funcoes:
                funcoes.append(fn)

    if not funcoes:
        if "seno" in tema.lower() or "cosseno" in tema.lower() or "trigonom" in tema.lower():
            funcoes = ["y = sin(x)"]
        elif "parábola" in tema.lower() or "quadrática" in tema.lower() or "2 grau" in tema.lower():
            funcoes = ["y = x^2"]

    if not funcoes:
        return content

    novas_funcoes = [fn for fn in funcoes[:2] if fn.strip().lower() not in funcoes_existentes]
    if not novas_funcoes:
        return content

    visuais = [
        {
            "tipo": "visual",
            "visual": {
                "tipo": "grafico",
                "descricao": f"Gráfico de apoio para interpretar {tema} de forma visual e objetiva.",
                "funcao": fn,
            },
        }
        for fn in novas_funcoes
    ]

    # Insere os visuais próximo do conceito + exemplo (e não no fim repetidamente)
    pos_explicacao = next((i for i, b in enumerate(blocos) if b.get("tipo") == "explicacao"), 0)
    pos_exemplo = next((i for i, b in enumerate(blocos) if b.get("tipo") == "exemplo"), None)

    if pos_exemplo is not None and pos_exemplo > pos_explicacao:
        # 1º visual após explicação, 2º antes do exemplo
        blocos.insert(pos_explicacao + 1, visuais[0])
        if len(visuais) > 1:
            pos_exemplo = next((i for i, b in enumerate(blocos) if b.get("tipo") == "exemplo"), pos_exemplo)
            blocos.insert(pos_exemplo, visuais[1])
    else:
        for offset, vb in enumerate(visuais, start=1):
            blocos.insert(pos_explicacao + offset, vb)
    content["blocos"] = blocos
    return content

def gerar_conteudo(materia: str, tema: str, foco_delimitado: str = "") -> dict:
    cached = get_cached_content(materia, tema, foco_delimitado)
    if cached:
        cached = _injetar_visuais_automaticos(cached, tema)
        # Prependa a mensagem amigável no início da explicação para não quebrar o frontend
        mensagem = gerar_mensagem_amigo(tema)
        blocos = cached.get("blocos", [])
        if blocos and blocos[0].get("tipo") == "explicacao":
            conteudo_atual = blocos[0].get("conteudo", "")
            if f"**{mensagem}**" not in conteudo_atual:
                blocos[0]["conteudo"] = f"**{mensagem}**\n\n{conteudo_atual}"
        quality = avaliar_qualidade_aula(cached)
        return {**cached, "cache": True, "quality": quality, "prompt_version": "v2-mentor"}

    # A limitação drástica (FREE_DAILY_LIMIT) foi desativada durante os testes/desenvolvimento
    # para garantir que os testes massivos não ativem bloqueios artificiais silenciando a OpenAI.

    prompt = f"""Você é o Amigo Elite, um mentor pedagógico de altíssimo nível.
Sua tarefa é gerar uma missão Socrática de Micro-learning, focando fortemente em ancoragem emocional e analogias marcantes, antes da matemática ou regra formal.

Matéria: {materia}
Tema: {tema}
Foco Específico: {foco_delimitado}

REGRAS OBRIGATÓRIAS DE DIDÁTICA SOCRÁTICA E ELITE:
- A aula DEVE sempre começar com uma analogia visual absurda, criativa ou de alto impacto financeiro/emocional/cotidiano para ancorar o tema no cérebro.
- Não comece com definições chatas como "X é Y". Comece com "Imagine que..."
- A linguagem deve ser de um mentor de elite: direto, incisivo, instigante, que faz o aluno se sentir inteligente. Use sempre "você".
- Ensine SOMENTE o recorte solicitado.
- Use formatação Markdown. Cifrões simples para matemática em linha (`$x^2$`) e duplos isolados (`$$x^2$$`). PROIBIDO usar `\\[ ... \\]` ou `\\( ... \\)`.

Formato OBRIGATÓRIO do JSON de saída (Respeite a ordem dos blocos):
{{
  "blocos": [
    {{
      "tipo": "explicacao",
      "conteudo": "1) A Analogia Elite (Crie uma âncora memorável). 2) A Regra Real (traduza a analogia para o conceito técnico em 2 frases). 3) A Armadilha Comum (o que a maioria erra)."
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
      "conteudo": "O 'Missão na Prática': um exemplo desafiador, resolvido num esquema passo a passo de raciocínio, e não apenas uma conta jogada."
    }},
    {{
      "tipo": "exercicios",
      "lista": ["Uma questão que exige interpretação usando a analogia criada", "Uma questão direta de cálculo/aplicação do tema"]
    }}
  ]
}}

REGRAS DOS EXERCÍCIOS:
- Exatamente 2 exercícios.
- Um de nível básico e outro intermediário.
- Não repetir o exemplo já resolvido.
- Não incluir gabarito dentro do bloco de exercícios.

REGRAS DE VISUAIS:
- Se precisar mostrar uma função matemática (parábola, reta, etc), passe a equação matemática real no campo "funcao" (ex: "y = x^2"). O nosso motor criará os dados e gráficos reais interativos.
- Para outros gráficos/tabelas preencha o campo "dados".
- NÃO gere HTML, não gere Markdown de imagens, nem links Pollinations. Apenas JSON estruturado puro.

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
        content = _injetar_visuais_automaticos(content, tema)
        content = revisar_aula(content)
        set_cached_content(materia, tema, foco_delimitado, content)

    mensagem = gerar_mensagem_amigo(tema)

    # Injeta a mensagem no primeiro bloco de explicacao ou adiciona no topo
    blocos = content.get("blocos", [])
    if blocos and blocos[0].get("tipo") == "explicacao":
        explicacao_atual = blocos[0].get("conteudo", "")
        blocos[0]["conteudo"] = f"**{mensagem}**\n\n{explicacao_atual}"
    else:
        blocos.insert(0, {"tipo": "explicacao", "conteudo": f"**{mensagem}**"})

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


def avaliar_resposta_exercicio(tema: str, enunciado: str, resposta_usuario: str) -> dict:
    prompt = f"""Atuando como o "Amigo Elite" avaliando uma resposta durante o Micro-learning:
Tema da Aula: {tema}
Pergunta Feita: {enunciado}
Resposta do Aluno: {resposta_usuario}

Sua tarefa é ler a resposta e avaliar a intuição e raciocínio por trás dela.

REGRAS DE AVALIAÇÃO ELITE:
1. O FOCO É SOCRÁTICO: Ignore erros de digitação ou respostas "feias". O aluno pegou o "pulo do gato"? Ele entendeu a essência? Se sim, considere correto.
2. FEEDBACK CURTO DE IMPACTO: Responda em no MÁXIMO 2 frases. Use tom de recompensa. Se acertou, valide o raciocínio dele de forma empolgante ("Baita sacada! Exatamente isso..."). Se errou, não dê sermão, faça ele pensar ("Quase. Mas lembra da analogia que a gente viu? O que aconteceria se...").
3. NUNCA DEIXE A RESPOSTA PURA NO FEEDBACK SE ELE ERROU: Dê apenas uma forte pista pra ele continuar a missão.

Retorne ESTRITAMENTE o formato JSON a seguir:
{{
  "correto": true ou false,
  "feedback": "Feedback de Elite: empolgante, recompensador se acertou, intrigante e socrático se errou. Máx 2 frases curtas."
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
Sua tarefa é dividir o tema principal em submissões (subtemas) para uma trilha de Micro-learning Socrático de Elite.

Tema: {tema}

Regras ABSOLUTAS:
1. Você DEVE quebrar o tema na quantidade sugerida: {qtd_sugerida} submissões.
2. Nomes impactantes: O campo "nome" deve ser curto mas instigante (Ex: "A Anatomia da Equação", e não apenas "Equação Básica").
3. DIRETO AO PONTO: É ABSOLUTAMENTE PROIBIDO gerar tópicos de revisão genérica inicial.
4. O campo "foco_delimitado" DEVE guiar o conteúdo a focar em 1 ou 2 conceitos-chave e instruir explicitamente qual analogia central pode ser usada lá.

Retorne ESTRITAMENTE um objeto JSON no formato abaixo:
{{
  "subtemas": [
    {{
      "nome": "Nome Curto e Impactante",
      "foco_delimitado": "Foco estrito do que ensinar + sugestão curta de analogia a usar."
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
