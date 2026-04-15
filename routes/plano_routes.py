from flask import Blueprint, jsonify, request

from services.plano_service import buscar_plano, gerar_plano_inicial

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
