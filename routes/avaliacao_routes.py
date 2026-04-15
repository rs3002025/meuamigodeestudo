from flask import Blueprint, jsonify

from services.ia_service import gerar_avaliacao_invisivel
from services.plano_service import buscar_plano

avaliacao_bp = Blueprint("avaliacao", __name__)


@avaliacao_bp.get("/<user_id>/surpresa")
def avaliacao_surpresa(user_id: str):
    plano = buscar_plano(user_id)
    if not plano:
        return jsonify({"erro": "Plano não encontrado."}), 404

    avaliacao = gerar_avaliacao_invisivel(plano["objetivo"])
    return jsonify(avaliacao)
