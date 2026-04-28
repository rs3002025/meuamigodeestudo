import sympy as sp
import numpy as np
import logging
import re

logger = logging.getLogger(__name__)

def gerar_pontos_funcao(funcao: str):
    try:
        if len((funcao or "").strip()) > 120:
            return [], []
        # Prepara a string da função
        expr_str = re.sub(r"^\s*y\s*=\s*", "", funcao.lower()).replace("^", "**")
        expr_str = expr_str.replace("$$", "").replace("$", "").strip()

        # Evita gráficos inválidos com parâmetros simbólicos (a, b, etc.) sem valor numérico
        simbolos_invalidos = re.findall(r"[a-wyz]", expr_str)
        if simbolos_invalidos:
            return [], []

        # Usa sympy para fazer parse seguro da expressão matemática e avaliar para os valores de x
        x_sym = sp.Symbol('x')
        expr = sp.sympify(expr_str)

        # Cria uma lista menor e mais pedagógica de pontos entre -6 e 6
        x_vals = np.linspace(-6, 6, 13)
        y_vals = []

        for x_val in x_vals:
            # Avalia a expressão para o valor de x atual
            y = expr.evalf(subs={x_sym: x_val})
            y_vals.append(round(float(y), 2))

        # Precisamos retornar como list() para que a serialização JSONB do db.py não quebre
        return [round(float(x), 2) for x in x_vals], y_vals

    except Exception as e:
        logger.warning("Erro função: %s", e)
        return [], []

def processar_visual(visual: dict):
    if visual.get("tipo") != "grafico":
        return visual

    # Se a IA informar a função matemática, nós geramos os pontos pra ela.
    # Ex: "funcao": "y = x^2 - 4x + 3"
    funcao_str = visual.get("funcao") or visual.get("dados", {}).get("funcao")
    if funcao_str:
        x, y = gerar_pontos_funcao(funcao_str)
        if x and y:
            # Cria ou recria o 'dados' com as arrays que o frontend precisa
            visual["dados"] = {"x": x, "y": y}
        else:
            # Fallback para casos conceituais (ex: y = ax + b)
            visual["tipo"] = "diagrama"

    return visual

def processar_aula(parsed: dict) -> dict:
    blocos = parsed.get("blocos", [])

    for bloco in blocos:
        if bloco["tipo"] == "visual" and "visual" in bloco:
            bloco["visual"] = processar_visual(bloco["visual"])

    return {"blocos": blocos}
