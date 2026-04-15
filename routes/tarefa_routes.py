from flask import Blueprint, jsonify, request

from services.ia_service import classificar_erro
from services.node_service import gerar_mensagem_diaria
from services.plano_service import ajustar_plano_com_desempenho, buscar_plano
from services.tarefa_service import buscar_tarefas_do_dia, concluir_tarefa, gerar_tarefas_diarias

tarefa_bp = Blueprint("tarefas", __name__)


@tarefa_bp.post("/gerar")
def gerar_tarefas():
    body = request.get_json(silent=True) or {}
    user_id = body.get("userId")
    plano = buscar_plano(user_id) if user_id else None

    if not plano:
        return jsonify({"erro": "Crie um plano antes de gerar tarefas."}), 404

    tarefas = gerar_tarefas_diarias(user_id, plano)
    mensagem = gerar_mensagem_diaria(0.7, 0)
    return jsonify({"mensagem": mensagem, "tarefas": tarefas}), 201


@tarefa_bp.get("/<user_id>/hoje")
def tarefas_hoje(user_id: str):
    tarefas = buscar_tarefas_do_dia(user_id)
    pendencias = len([t for t in tarefas if t["status"] != "concluida"])
    mensagem = gerar_mensagem_diaria(0.7, pendencias)
    return jsonify({"mensagem": mensagem, "tarefas": tarefas})


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

    return jsonify({"planoAtualizado": plano_atualizado, "errosClassificados": erros_classificados})
