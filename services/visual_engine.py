import sympy as sp
import numpy as np
import logging
import re

logger = logging.getLogger(__name__)


def _pontos_conceituais(expr_str: str):
    x_vals = np.linspace(-4, 4, 9)
    if "a*x" in expr_str or "ax" in expr_str or "x+b" in expr_str or "x + b" in expr_str:
        y_vals = [round(1.5 * float(x) + 1, 2) for x in x_vals]
        return [round(float(x), 2) for x in x_vals], y_vals
    if "^x" in expr_str or "**x" in expr_str or "exp" in expr_str:
        y_vals = [round(float(2 ** x), 2) for x in x_vals]
        return [round(float(x), 2) for x in x_vals], y_vals
    return [], []


def gerar_pontos_funcao(funcao: str):
    try:
        if len((funcao or "").strip()) > 120:
            return [], []
        # Prepara a string da função
        expr_str = re.sub(r"^\s*y\s*=\s*", "", funcao.lower()).replace("^", "**")
        expr_str = expr_str.replace("$$", "").replace("$", "").strip()
        expr_str = re.sub(r"(?<=\d)\s*(?=[a-z(])", "*", expr_str)   # 4x -> 4*x
        expr_str = re.sub(r"(?<=[a-z)])\s*(?=\d)", "*", expr_str)   # x2 -> x*2
        expr_str = re.sub(r"(?<=[a-z)])\s*(?=\()", "*", expr_str)   # x(x+1) -> x*(x+1)

        # Evita gráficos inválidos com parâmetros simbólicos (a, b, etc.) sem valor numérico
        simbolos_invalidos = re.findall(r"[a-wyz]", expr_str)
        if simbolos_invalidos:
            return _pontos_conceituais(expr_str)

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
    # Se a IA informar a função matemática, nós geramos os pontos pra ela.
    # Ex: "funcao": "y = x^2 - 4x + 3"
    funcao_str = visual.get("funcao") or visual.get("dados", {}).get("funcao")
    if funcao_str:
        visual["tipo"] = "grafico"
        x, y = gerar_pontos_funcao(funcao_str)
        if x and y:
            # Cria ou recria o 'dados' com as arrays que o frontend precisa
            visual["dados"] = {"x": x, "y": y}
        else:
            # Fallback para casos conceituais (ex: y = ax + b)
            visual["tipo"] = "diagrama"
        return visual

    if visual.get("tipo") != "grafico":
        return visual

    return visual

def processar_aula(parsed: dict) -> dict:
    blocos = parsed.get("blocos", [])

    for bloco in blocos:
        if bloco["tipo"] == "visual" and "visual" in bloco:
            bloco["visual"] = processar_visual(bloco["visual"])

    return {"blocos": blocos}
