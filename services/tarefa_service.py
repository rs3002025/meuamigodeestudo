from datetime import datetime, timezone

from services.db import memory


def _hoje() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def minutos_por_bloco(carga_diaria: int) -> dict:
    teoria = round(carga_diaria * 0.4)
    questoes = round(carga_diaria * 0.4)
    revisao = max(10, carga_diaria - teoria - questoes)
    return {"teoria": teoria, "questoes": questoes, "revisao": revisao}


def gerar_tarefas_diarias(user_id: str, plano: dict) -> list[dict]:
    hoje = _hoje()
    blocos = minutos_por_bloco(plano["cargaDiaria"])

    tarefas = [
        {
            "id": f"{hoje}-1",
            "ordem": 1,
            "tipo": "estudo",
            "titulo": f"Bloco de teoria ({blocos['teoria']} min)",
            "status": "pendente",
            "podePular": False,
        },
        {
            "id": f"{hoje}-2",
            "ordem": 2,
            "tipo": "questoes",
            "titulo": f"Questões guiadas ({blocos['questoes']} min)",
            "status": "pendente",
            "podePular": False,
        },
        {
            "id": f"{hoje}-3",
            "ordem": 3,
            "tipo": "revisao",
            "titulo": f"Revisão ativa ({blocos['revisao']} min)",
            "status": "pendente",
            "podePular": False,
        },
    ]

    memory.tasks[f"{user_id}:{hoje}"] = tarefas
    return tarefas


def buscar_tarefas_do_dia(user_id: str, data: str | None = None) -> list[dict]:
    chave = f"{user_id}:{data or _hoje()}"
    return memory.tasks.get(chave, [])


def concluir_tarefa(user_id: str, task_id: str, data: str | None = None) -> tuple[dict, int]:
    chave = f"{user_id}:{data or _hoje()}"
    tarefas = memory.tasks.get(chave, [])

    idx = next((i for i, t in enumerate(tarefas) if t["id"] == task_id), -1)
    if idx < 0:
        return {"erro": "Tarefa não encontrada."}, 400

    pendente_anterior = next((t for t in tarefas[:idx] if t["status"] != "concluida"), None)
    if pendente_anterior:
        return {"erro": "Fluxo sequencial ativo. Conclua a tarefa anterior primeiro."}, 400

    tarefas[idx] = {**tarefas[idx], "status": "concluida", "concluidaEm": _agora_iso()}
    memory.tasks[chave] = tarefas
    return {"tarefas": tarefas}, 200
