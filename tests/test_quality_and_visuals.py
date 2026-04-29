import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from services.quality_guard import avaliar_qualidade_aula
from services.ia_service import _injetar_visuais_automaticos


def test_quality_guard_basico():
    aula = {
        "blocos": [
            {"tipo": "explicacao", "conteudo": "O que é... passo... erros..."},
            {"tipo": "exemplo", "conteudo": "Exemplo"},
            {"tipo": "exercicios", "lista": ["q1", "q2"]},
        ]
    }
    res = avaliar_qualidade_aula(aula)
    assert res["aprovado"] is True
    assert res["score"] >= 70


def test_injecao_visual_sem_duplicar():
    aula = {
        "blocos": [
            {"tipo": "explicacao", "conteudo": "Use y = x^2 para entender"},
            {"tipo": "visual", "visual": {"tipo": "grafico", "funcao": "y = x^2"}},
            {"tipo": "exemplo", "conteudo": "Aplicando"},
        ]
    }
    out = _injetar_visuais_automaticos(aula, "função quadrática")
    visuais = [b for b in out["blocos"] if b.get("tipo") == "visual"]
    assert len(visuais) == 1
