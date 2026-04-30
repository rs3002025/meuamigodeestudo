import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from services.quality_guard import avaliar_qualidade_aula


def test_quality_guard_basico():
    aula = {
        "blocos": [
            {"tipo": "explicacao", "conteudo": "Imagine uma analogia onde a matemática é..."},
            {"tipo": "exemplo", "conteudo": "Exemplo"},
            {"tipo": "exercicios", "lista": ["q1", "q2"]},
        ]
    }
    res = avaliar_qualidade_aula(aula)
    assert res["aprovado"] is True
    assert res["score"] >= 70
