from datetime import datetime, timezone

from services.db import get_user_metrics, memory

CARGA_POR_NIVEL = {
    "iniciante": 40,
    "intermediario": 70,
    "avancado": 90,
}


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def calcular_carga_diaria(tempo_disponivel_min: int, nivel: str) -> int:
    fator = CARGA_POR_NIVEL.get(nivel, 60)
    return max(20, min(tempo_disponivel_min, fator))


def _objetivo_para_lista(objetivo: str | list[str]) -> list[str]:
    if isinstance(objetivo, list):
        return [str(o).strip() for o in objetivo if str(o).strip()]
    if isinstance(objetivo, str) and objetivo.strip():
        return [objetivo.strip()]
    return []


def gerar_plano_inicial(payload: dict) -> dict:
    user_id = payload["userId"]
    tempo_disponivel_min = int(payload.get("tempoDisponivelMin", 60))
    nivel = payload.get("nivel", "intermediario")

    materias = payload.get("materias") or _objetivo_para_lista(payload.get("objetivo"))

    plano = {
        "userId": user_id,
        "objetivo": payload["objetivo"],
        "materias": materias,
        "nivel": nivel,
        "modo": payload.get("modo", "personalizado"),
        "tipo": payload.get("tipo", "escola"),
        "cargaDiaria": calcular_carga_diaria(tempo_disponivel_min, nivel),
        "focoAtual": ["teoria", "questoes", "revisao"],
        "versao": 1,
        "criadoEm": _agora_iso(),
        "atualizadoEm": _agora_iso(),
    }

    memory.plans[user_id] = plano
    get_user_metrics(user_id)
    return plano


def buscar_plano(user_id: str) -> dict | None:
    return memory.plans.get(user_id)


def ajustar_plano_com_desempenho(user_id: str, desempenho_dia: dict) -> dict | None:
    plano = memory.plans.get(user_id)
    if not plano:
        return None

    taxa_acerto = float(desempenho_dia.get("taxaAcerto", 0))
    erros_recorrentes = int(desempenho_dia.get("errosRecorrentes", 0))

    carga_diaria = plano["cargaDiaria"]
    foco_atual = list(plano["focoAtual"])

    if taxa_acerto < 0.6:
        carga_diaria = max(25, carga_diaria - 10)
        foco_atual = ["reforco materia fraca", "questoes comentadas", "revisao ativa"]
    elif taxa_acerto > 0.8 and erros_recorrentes <= 1:
        carga_diaria = min(120, carga_diaria)
        foco_atual = ["conteudo novo", "questoes mistas", "menos repeticao"]

    atualizado = {
        **plano,
        "cargaDiaria": carga_diaria,
        "focoAtual": foco_atual,
        "versao": plano["versao"] + 1,
        "atualizadoEm": _agora_iso(),
    }

    memory.plans[user_id] = atualizado

    metrics = get_user_metrics(user_id)
    metrics["ultima_taxa_acerto"] = taxa_acerto
    return atualizado
