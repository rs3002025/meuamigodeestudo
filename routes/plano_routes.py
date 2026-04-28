from flask import Blueprint, jsonify, request

from services.plano_service import buscar_plano, gerar_plano_inicial, ajustar_plano_por_prazo
from services.validation import parse_int

plano_bp = Blueprint("plano", __name__)


@plano_bp.post("/iniciar")
def iniciar_plano():
    body = request.get_json(silent=True) or {}

    if not body.get("userId") or not body.get("objetivo"):
        return jsonify({"erro": "userId e objetivo são obrigatórios."}), 400

    plano = gerar_plano_inicial(body)
    return jsonify({"plano": plano}), 201


@plano_bp.get("/<user_id>")
def get_plano(user_id: str):
    plano = buscar_plano(user_id)
    if not plano:
        return jsonify({"erro": "Plano não encontrado."}), 404
    return jsonify({"plano": plano})


@plano_bp.post("/<user_id>/deadline")
def definir_deadline(user_id: str):
    body = request.get_json(silent=True) or {}
    dias, erro = parse_int(body.get("diasAteProva"), None)
    if erro or dias is None or dias < 0:
        return jsonify({"erro": "diasAteProva inválido."}), 400

    plano = ajustar_plano_por_prazo(user_id, dias)
    if not plano:
        return jsonify({"erro": "Plano não encontrado."}), 404
    return jsonify({"plano": plano}), 200
