import json
from datetime import datetime, timezone
from services.db import get_user_metrics, get_db_connection
from services.ia_service import gerar_estrutura_tema

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

    # Nova arquitetura: Gerar blocos de subtemas para a trilha
    trilha_subtemas = []

    # Se há matérias, geramos subtemas para a primeira (ou todas). Para manter simples, vamos gerar para a primeira matéria (que geralmente é o foco principal).
    # Se o objetivo é direto, quebramos ele.
    foco = materias[0] if materias else str(payload.get("objetivo", ""))
    if foco:
        subtemas = gerar_estrutura_tema(foco)
        for subtema in subtemas:
            trilha_subtemas.append({"materia": foco, "tema": subtema, "tipo": "teoria"})
            trilha_subtemas.append({"materia": foco, "tema": subtema, "tipo": "questoes"})

    plano = {
        "userId": user_id,
        "objetivo": payload["objetivo"],
        "materias": materias,
        "nivel": nivel,
        "modo": payload.get("modo", "personalizado"),
        "tipo": payload.get("tipo", "escola"),
        "cargaDiaria": calcular_carga_diaria(tempo_disponivel_min, nivel),
        "focoAtual": ["teoria", "questoes", "revisao"],
        "trilha_subtemas": trilha_subtemas,
        "progresso_trilha": 0,
        "versao": 1,
        "criadoEm": _agora_iso(),
        "atualizadoEm": _agora_iso(),
    }

    # Ensure user exists
    get_user_metrics(user_id)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO plans (user_id, payload)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (user_id) DO UPDATE SET payload = EXCLUDED.payload
            """, (user_id, json.dumps(plano)))
            conn.commit()

    return plano

def buscar_plano(user_id: str) -> dict | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payload FROM plans WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            return row["payload"] if row else None

def ajustar_plano_com_desempenho(user_id: str, desempenho_dia: dict) -> dict | None:
    plano = buscar_plano(user_id)
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

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE plans SET payload = %s::jsonb WHERE user_id = %s", (json.dumps(atualizado), user_id))
            cur.execute("UPDATE users SET ultima_taxa_acerto = %s WHERE id = %s", (taxa_acerto, user_id))
            conn.commit()

    return atualizado
