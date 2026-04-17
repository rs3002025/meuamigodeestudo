from flask import Blueprint, jsonify, request

from services.db import get_user_metrics, atualizar_dias_sem_estudar
from services.ia_service import classificar_erro, talvez_gerar_avaliacao_invisivel
from services.node_service import gerar_mensagem_diaria
from services.plano_service import ajustar_plano_com_desempenho, buscar_plano
from services.tarefa_service import buscar_tarefas_do_dia, concluir_tarefa, gerar_tarefas_diarias

tarefa_bp = Blueprint("tarefas", __name__)


def _materia_do_dia(tarefas: list[dict]) -> str | None:
    if not tarefas:
        return None
    pendente = next((t for t in tarefas if t.get("status") != "concluida"), tarefas[0])
    return pendente.get("materia")


@tarefa_bp.post("/gerar")
def gerar_tarefas():
    body = request.get_json(silent=True) or {}
    user_id = body.get("userId")
    plano = buscar_plano(user_id) if user_id else None

    if not plano:
        return jsonify({"erro": "Crie um plano antes de gerar tarefas."}), 404

    tarefas = gerar_tarefas_diarias(user_id, plano)
    metrics = atualizar_dias_sem_estudar(user_id)
    mensagem = gerar_mensagem_diaria(
        taxa_acerto=float(metrics.get("ultima_taxa_acerto") or 0.7),
        pendencias=len(tarefas),
        dias_sem_estudar=int(metrics.get("dias_sem_estudar") or 0),
        dias_consecutivos=int(metrics.get("dias_consecutivos") or 0),
        materia_do_dia=_materia_do_dia(tarefas),
    )

    avaliacao_surpresa = talvez_gerar_avaliacao_invisivel(
        plano["objetivo"],
        metrics.get("conteudos_recentes_avaliacao", []),
    )
    if avaliacao_surpresa:
        tema = avaliacao_surpresa["questoes"][0]["tema"]
        recentes = metrics.get("conteudos_recentes_avaliacao", [])
        metrics["conteudos_recentes_avaliacao"] = (recentes + [tema])[-3:]

    return jsonify({"mensagem": mensagem, "tarefas": tarefas, "extra": avaliacao_surpresa}), 201


@tarefa_bp.get("/<user_id>/hoje")
def tarefas_hoje(user_id: str):
    tarefas = buscar_tarefas_do_dia(user_id)
    metrics = atualizar_dias_sem_estudar(user_id)
    pendencias = len([t for t in tarefas if t["status"] != "concluida"])

    mensagem = gerar_mensagem_diaria(
        taxa_acerto=float(metrics.get("ultima_taxa_acerto") or 0.7),
        pendencias=pendencias,
        dias_sem_estudar=int(metrics.get("dias_sem_estudar") or 0),
        dias_consecutivos=int(metrics.get("dias_consecutivos") or 0),
        materia_do_dia=_materia_do_dia(tarefas),
    )
    return jsonify({"mensagem": mensagem, "tarefas": tarefas, "streak": metrics.get("dias_consecutivos", 0)})


@tarefa_bp.post("/<user_id>/concluir")
def concluir(user_id: str):
    body = request.get_json(silent=True) or {}
    task_id = body.get("taskId")
    if not task_id:
        return jsonify({"erro": "taskId é obrigatório."}), 400

    payload, status_code = concluir_tarefa(user_id, task_id)
    return jsonify(payload), status_code


@tarefa_bp.post("/<user_id>/desempenho")
def desempenho(user_id: str):
    body = request.get_json(silent=True) or {}
    taxa_acerto = float(body.get("taxaAcerto", 0))
    erros = body.get("erros", [])

    erros_classificados = []
    for erro in erros:
        classe = classificar_erro(erro.get("respostaCorreta", ""), erro.get("respostaUsuario", ""))
        erros_classificados.append({**erro, "classe": classe})

    recorrentes = len([erro for erro in erros_classificados if erro["classe"] == "conteudo"])
    plano_atualizado = ajustar_plano_com_desempenho(
        user_id,
        {"taxaAcerto": taxa_acerto, "errosRecorrentes": recorrentes},
    )

    if not plano_atualizado:
        return jsonify({"erro": "Plano não encontrado."}), 404

    metrics = get_user_metrics(user_id)
    return jsonify(
        {
            "planoAtualizado": plano_atualizado,
            "errosClassificados": erros_classificados,
            "resumo": {"taxaAcerto": taxa_acerto, "streak": metrics.get("dias_consecutivos", 0)},
        }
    )
