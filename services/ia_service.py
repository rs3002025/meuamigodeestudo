import random
import re
import unicodedata
from datetime import datetime, timezone


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
