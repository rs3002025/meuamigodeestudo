import sympy as sp
import numpy as np

def gerar_pontos_funcao(funcao: str):
    try:
        # Prepara a string da função
        expr_str = funcao.lower().replace("y=", "").replace("^", "**")

        # Usa sympy para fazer parse seguro da expressão matemática e avaliar para os valores de x
        x_sym = sp.Symbol('x')
        expr = sp.sympify(expr_str)

        # Cria uma lista de 50 pontos entre -10 e 10
        x_vals = np.linspace(-10, 10, 50)
        y_vals = []

        for x_val in x_vals:
            # Avalia a expressão para o valor de x atual
            y = expr.evalf(subs={x_sym: x_val})
            y_vals.append(float(y))

        # Precisamos retornar como list() para que a serialização JSONB do db.py não quebre
        return [float(x) for x in x_vals], y_vals

    except Exception as e:
        print("Erro função:", e)
        return [], []

def processar_visual(visual: dict):
    if visual.get("tipo") != "grafico":
        return visual

    # Se a IA informar a função matemática, nós geramos os pontos pra ela.
    # Ex: "funcao": "y = x^2 - 4x + 3"
    funcao_str = visual.get("funcao") or visual.get("dados", {}).get("funcao")
    if funcao_str:
        x, y = gerar_pontos_funcao(funcao_str)
        # Cria ou recria o 'dados' com as arrays que o frontend precisa
        visual["dados"] = {"x": x, "y": y}

    return visual

def processar_aula(parsed: dict) -> dict:
    blocos = parsed.get("blocos", [])

    for bloco in blocos:
        if bloco["tipo"] == "visual" and "visual" in bloco:
            bloco["visual"] = processar_visual(bloco["visual"])

    return {"blocos": blocos}
