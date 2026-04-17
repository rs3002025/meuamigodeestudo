import re
import unicodedata

from services.ia_service import normalizar_lista_conteudos


def detectar_tipo_objetivo(objetivo: str) -> str:
    raw = (objetivo or "").strip().lower()
    if not raw:
        return "outro"

    concurso_terms = ["concurso", "edital", "enem", "oab", "vestibular", "pm", "pc", "inss"]
    escola_terms = ["escola", "prova", "bimestre", "faculdade", "matéria", "materia"]

    if any(term in raw for term in concurso_terms):
        return "concurso"
    if any(term in raw for term in escola_terms):
        return "escola"
    return "outro"


def _slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", ascii_text.strip().lower())


def _normalizar_conteudos(raw: str) -> list[str]:
    return normalizar_lista_conteudos(raw)


def processar_onboarding(payload: dict) -> tuple[dict | None, str | None]:
    user_id = (payload.get("userId") or "").strip()
    objetivo = (payload.get("objetivo") or "").strip()

    if not user_id:
        return None, "userId é obrigatório"
    if not objetivo:
        return None, "me diz o que tu quer estudar"

    tipo = payload.get("tipo") or detectar_tipo_objetivo(objetivo)
    modo = "personalizado"
    materias: list[str] = []

    if tipo == "concurso":
        tem_conteudo = _slug(str(payload.get("temConteudo") or ""))
        if tem_conteudo in {"sim", "s"}:
            materias = _normalizar_conteudos(payload.get("conteudo") or "")
            if len(materias) < 1:
                return None, "preciso pelo menos das matérias principais"
        else:
            modo = "generico"
    else:
        materias = _normalizar_conteudos(payload.get("conteudo") or "")
        if len(materias) < 1:
            if bool(payload.get("aceitarGenerico")):
                modo = "generico"
            else:
                return None, "sem os temas não consigo montar um plano eficaz"

    plano_payload = {
        "userId": user_id,
        "objetivo": materias if materias else objetivo,
        "materias": materias,
        "modo": modo,
        "tipo": tipo,
        "nivel": payload.get("nivel", "intermediario"),
        "tempoDisponivelMin": int(payload.get("tempoDisponivelMin", 60)),
    }

    return plano_payload, None
