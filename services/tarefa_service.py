import json
from datetime import datetime, timezone

from services.db import registrar_estudo, get_db_connection
from services.ia_service import gerar_conteudo
from services.node_service import feedback_conclusao

def _hoje() -> str:
    return datetime.now(timezone.utc).date().isoformat()

def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _temas_padrao(materia: str) -> list[str]:
    m = materia.lower()
    if "matem" in m:
        return ["frações", "equações", "problemas práticos"]
    if "portugu" in m:
        return ["interpretação", "gramática", "texto e sentido"]
    return ["fundamentos", "aplicação", "fixação"]

def gerar_tarefas_diarias(user_id: str, plano: dict) -> list[dict]:
    hoje = _hoje()

    trilha_subtemas = plano.get("trilha_subtemas", [])
    progresso_trilha = plano.get("progresso_trilha", 0)

    # Entrega a trilha toda, sem limites de blocos por dia. O usuário faz no próprio ritmo.
    # Pegamos tudo a partir do progresso atual. Se já terminou tudo, reentrega os últimos.
    etapas_dinamicas = trilha_subtemas[progresso_trilha:]

    if not etapas_dinamicas and trilha_subtemas:
        etapas_dinamicas = trilha_subtemas[-4:] # Apenas um fallback para não dar tela em branco

    tarefas: list[dict] = []

    from services.db import increment_ia_daily_count

    for idx, etapa in enumerate(etapas_dinamicas):
        materia = etapa.get("materia", "Geral")
        tema = etapa.get("tema", "Fundamentos")
        tipo = etapa.get("tipo", "teoria")
        foco_delimitado = etapa.get("foco_delimitado", "")

        conteudo = gerar_conteudo(materia, tema, foco_delimitado)

        # O incremento era feito dentro do gerar_conteudo original.
        # Agora o IA service não sabe do usuário, então controlamos o rate aqui
        if not conteudo.get("cache"):
            increment_ia_daily_count(user_id)

        tarefas.append(
            {
                "id": f"{hoje}-{idx + 1}",
                "ordem": idx + 1,
                "tipo": tipo,
                "materia": materia,
                "tema": tema,
                "descricao": tema,
                "conteudo": conteudo,
                "status": "pendente",
                "podePular": False,
            }
        )

    # Avançar progresso na trilha do plano
    novo_progresso = progresso_trilha + len(etapas_dinamicas)
    plano["progresso_trilha"] = novo_progresso

    task_key = f"{user_id}:{hoje}"
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO tasks (id, user_id, data_ref, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload
            """, (task_key, user_id, hoje, json.dumps(tarefas)))

            # Atualiza também o plano do usuário com o novo progresso
            cur.execute("""
                UPDATE plans SET payload = %s::jsonb WHERE user_id = %s
            """, (json.dumps(plano), user_id))

            conn.commit()

    return tarefas

def buscar_tarefas_do_dia(user_id: str, data: str | None = None) -> list[dict]:
    hoje = data or _hoje()
    task_key = f"{user_id}:{hoje}"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payload FROM tasks WHERE id = %s", (task_key,))
            row = cur.fetchone()
            return row["payload"] if row else []

def concluir_tarefa(user_id: str, task_id: str, data: str | None = None) -> tuple[dict, int]:
    hoje = data or _hoje()
    task_key = f"{user_id}:{hoje}"

    tarefas = buscar_tarefas_do_dia(user_id, data)

    idx = next((i for i, t in enumerate(tarefas) if t["id"] == task_id), -1)
    if idx < 0:
        return {"erro": "Tarefa não encontrada."}, 400

    pendente_anterior = next((t for t in tarefas[:idx] if t["status"] != "concluida"), None)
    if pendente_anterior:
        return {"erro": "Conclua a tarefa anterior primeiro"}, 400

    tarefas[idx] = {**tarefas[idx], "status": "concluida", "concluidaEm": _agora_iso()}

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE tasks SET payload = %s::jsonb WHERE id = %s", (json.dumps(tarefas), task_key))
            conn.commit()

    metricas = registrar_estudo(user_id)
    feedback = feedback_conclusao(tarefas[idx]["ordem"], len(tarefas))

    return {
        "tarefas": tarefas,
        "feedback": feedback,
        "diasConsecutivos": metricas["dias_consecutivos"],
    }, 200
