import sympy as sp
import numpy as np
import logging
import re
import io
import base64
import matplotlib
matplotlib.use('Agg')  # Configura para não precisar de display gráfico
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def gerar_grafico_base64(x_vals, y_vals, titulo="Gráfico"):
    try:
        plt.figure(figsize=(6, 4))
        plt.plot(x_vals, y_vals, color='#6366f1', linewidth=2.5, marker='o', markersize=4)

        # Estilização
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.axhline(0, color='black', linewidth=1)
        plt.axvline(0, color='black', linewidth=1)
        plt.title(titulo, fontsize=12, pad=10)
        plt.xlabel("x", fontsize=10)
        plt.ylabel("y", fontsize=10)

        # Remove bordas
        ax = plt.gca()
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Salva para base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        plt.close()

        img_str = base64.b64encode(buf.getvalue()).decode('utf-8')
        return img_str
    except Exception as e:
        logger.error("Erro gerando imagem base64 matplotlib: %s", e)
        plt.close()
        return None

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
        expr_str = re.sub(r"(?<=\))\s*(?=[a-z])", "*", expr_str)    # (x+1)x -> (x+1)*x

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
            y_float = float(y)
            if not np.isfinite(y_float):
                return [], []
            y_vals.append(round(y_float, 2))

        # Precisamos retornar como list() para que a serialização JSONB do db.py não quebre
        return [round(float(x), 2) for x in x_vals], y_vals

    except Exception as e:
        logger.warning("Erro função: %s", e)
        return [], []

def processar_visual(visual: dict):
    # Backward compatibility, visual node structure not used anymore, handled globally in processar_aula now
    return visual

def processar_aula(parsed: dict) -> dict:
    blocos = parsed.get("blocos", [])

    for bloco in blocos:
        if bloco["tipo"] == "grafico_matematico":
            funcao_str = bloco.get("funcao", "")
            if funcao_str:
                x, y = gerar_pontos_funcao(funcao_str)
                if x and y:
                    imagem_base64 = gerar_grafico_base64(x, y, titulo=f"Gráfico de: {funcao_str}")
                    if imagem_base64:
                        bloco["imagem_base64"] = imagem_base64

        # Legacy support
        elif bloco["tipo"] == "visual" and "visual" in bloco:
            bloco["visual"] = processar_visual(bloco["visual"])

    return {"blocos": blocos}
