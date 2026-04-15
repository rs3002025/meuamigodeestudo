from datetime import datetime, timezone

from services.db import memory

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


def gerar_plano_inicial(payload: dict) -> dict:
    user_id = payload["userId"]
    tempo_disponivel_min = int(payload.get("tempoDisponivelMin", 60))
    nivel = payload.get("nivel", "intermediario")

    plano = {
        "userId": user_id,
        "objetivo": payload["objetivo"],
        "nivel": nivel,
        "modo": payload.get("modo", "concurso"),
        "cargaDiaria": calcular_carga_diaria(tempo_disponivel_min, nivel),
        "focoAtual": ["teoria", "questoes", "revisao"],
        "versao": 1,
        "criadoEm": _agora_iso(),
        "atualizadoEm": _agora_iso(),
    }

    memory.plans[user_id] = plano
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

    if taxa_acerto < 0.55:
        carga_diaria = max(25, carga_diaria - 10)
        foco_atual = ["revisao guiada", "questoes comentadas", "micro resumo"]
    elif taxa_acerto > 0.8 and erros_recorrentes <= 1:
        carga_diaria = min(120, carga_diaria + 10)
        foco_atual = ["teoria avancada", "questoes mistas", "simulado rapido"]

    atualizado = {
        **plano,
        "cargaDiaria": carga_diaria,
        "focoAtual": foco_atual,
        "versao": plano["versao"] + 1,
        "atualizadoEm": _agora_iso(),
    }

    memory.plans[user_id] = atualizado
    return atualizado
