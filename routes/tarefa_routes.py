from flask import Blueprint, jsonify, request

from services.db import (
    get_user_metrics,
    atualizar_dias_sem_estudar,
    add_error_notebook_entry,
    get_error_notebook,
    log_telemetry,
)
from services.ia_service import classificar_erro, talvez_gerar_avaliacao_invisivel, recomendar_proximo_passo
from services.node_service import gerar_mensagem_diaria
from services.plano_service import ajustar_plano_com_desempenho, buscar_plano
from services.tarefa_service import buscar_tarefas_do_dia, concluir_tarefa, gerar_tarefas_diarias, gerar_simulado
from services.validation import parse_float, parse_int

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


@tarefa_bp.post("/<user_id>/avaliar-resposta")
def avaliar_resposta_usuario(user_id: str):
    body = request.get_json(silent=True) or {}
    tema = body.get("tema")
    enunciado = body.get("enunciado")
    resposta = body.get("resposta")

    if not tema or not enunciado or not resposta:
        return jsonify({"erro": "Tema, enunciado e resposta são obrigatórios."}), 400

    from services.ia_service import avaliar_resposta_exercicio
    resultado = avaliar_resposta_exercicio(tema, enunciado, resposta)
    log_telemetry(user_id, "resposta_avaliada", {"tema": tema, "correto": resultado.get("correto")})
    return jsonify(resultado), 200

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
    taxa_acerto, erro_taxa = parse_float(body.get("taxaAcerto"), 0.0)
    if erro_taxa:
        return jsonify({"erro": "taxaAcerto inválida."}), 400
    erros = body.get("erros", [])

    erros_classificados = []
    for erro in erros:
        classe = classificar_erro(erro.get("respostaCorreta", ""), erro.get("respostaUsuario", ""))
        erro_item = {**erro, "classe": classe}
        erros_classificados.append(erro_item)
        add_error_notebook_entry(
            user_id,
            {
                "tema": erro.get("tema", "geral"),
                "materia": erro.get("materia", "Geral"),
                "classe": classe,
                "timestamp": erro.get("timestamp"),
            },
        )

    recorrentes = len([erro for erro in erros_classificados if erro["classe"] == "conteudo"])
    plano_atualizado = ajustar_plano_com_desempenho(
        user_id,
        {"taxaAcerto": taxa_acerto, "errosRecorrentes": recorrentes},
    )

    if not plano_atualizado:
        return jsonify({"erro": "Plano não encontrado."}), 404

    metrics = get_user_metrics(user_id)
    proximo_passo = recomendar_proximo_passo(taxa_acerto, recorrentes)
    log_telemetry(user_id, "desempenho_registrado", {"taxaAcerto": taxa_acerto, "recorrentes": recorrentes})
    return jsonify(
        {
            "planoAtualizado": plano_atualizado,
            "errosClassificados": erros_classificados,
            "resumo": {
                "taxaAcerto": taxa_acerto,
                "streak": metrics.get("dias_consecutivos", 0),
                "proximoPasso": proximo_passo,
            },
        }
    )


@tarefa_bp.get("/<user_id>/error-notebook")
def error_notebook(user_id: str):
    return jsonify({"itens": get_error_notebook(user_id)})


@tarefa_bp.post("/<user_id>/simulado")
def simulado(user_id: str):
    body = request.get_json(silent=True) or {}
    tema = body.get("tema", "revisao geral")
    quantidade, erro_qtd = parse_int(body.get("quantidade"), 10)
    if erro_qtd or quantidade is None:
        return jsonify({"erro": "quantidade inválida"}), 400
    quantidade = min(max(3, quantidade), 30)
    return jsonify({"simulado": gerar_simulado(user_id, tema, quantidade)}), 201
