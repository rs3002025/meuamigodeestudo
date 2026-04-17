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
    materias = plano.get("materias") or []

    if not materias:
        objetivo = plano.get("objetivo")
        materias = objetivo if isinstance(objetivo, list) else [str(objetivo)]

    while len(materias) < 3:
        materias.append(materias[-1] if materias else "estudos gerais")

    tipos = ["teoria", "questoes", "revisao"]
    tarefas: list[dict] = []

    for idx in range(3):
        materia = materias[idx % len(materias)]
        tema = _temas_padrao(materia)[idx % 3]
        conteudo = gerar_conteudo(user_id, materia, tema)

        tarefas.append(
            {
                "id": f"{hoje}-{idx + 1}",
                "ordem": idx + 1,
                "tipo": tipos[idx],
                "materia": materia,
                "tema": tema,
                "descricao": f"{materia} — {tema} ({tipos[idx]})",
                "conteudo": conteudo,
                "status": "pendente",
                "podePular": False,
            }
        )

    task_key = f"{user_id}:{hoje}"
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO tasks (id, user_id, data_ref, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload
            """, (task_key, user_id, hoje, json.dumps(tarefas)))
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
