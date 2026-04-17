from flask import Blueprint, jsonify, request

from services.db import get_user_metrics
from services.node_service import gerar_mensagem_diaria
from services.onboarding_service import detectar_tipo_objetivo, processar_onboarding
from services.plano_service import gerar_plano_inicial
from services.tarefa_service import gerar_tarefas_diarias

onboarding_bp = Blueprint("onboarding", __name__)


@onboarding_bp.post("/detectar-tipo")
def detectar_tipo():
    body = request.get_json(silent=True) or {}
    objetivo = body.get("objetivo", "")
    if not str(objetivo).strip():
        return jsonify({"erro": "me diz o que tu quer estudar"}), 400

    tipo = detectar_tipo_objetivo(objetivo)
    return jsonify({"tipo": tipo})


@onboarding_bp.post("/finalizar")
def finalizar():
    body = request.get_json(silent=True) or {}
    plano_payload, erro = processar_onboarding(body)

    if erro:
        return jsonify({"erro": erro}), 400

    plano = gerar_plano_inicial(plano_payload)
    tarefas = gerar_tarefas_diarias(plano_payload["userId"], plano)

    metrics = get_user_metrics(plano_payload["userId"])
    mensagem = gerar_mensagem_diaria(
        taxa_acerto=float(metrics.get("ultima_taxa_acerto") or 0.7),
        pendencias=len(tarefas),
        dias_sem_estudar=int(metrics.get("dias_sem_estudar") or 0),
        dias_consecutivos=int(metrics.get("dias_consecutivos") or 0),
    )

    onboarding_meta = {
        "tipo": plano_payload["tipo"],
        "modo": plano_payload["modo"],
        "materias": plano_payload["materias"],
    }

    if plano_payload["modo"] == "generico":
        onboarding_meta["aviso"] = "vou montar algo genérico só pra te mostrar como funciona"

    return jsonify({"plano": plano, "tarefas": tarefas, "mensagem": mensagem, "onboarding": onboarding_meta}), 201
