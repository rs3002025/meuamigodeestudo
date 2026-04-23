import urllib.parse

def render_visual(visual: dict) -> str:
    if not visual:
        return ""

    tipo = visual.get("tipo")

    if tipo == "grafico":
        return gerar_grafico_dinamico(visual)

    if tipo == "tabela":
        return gerar_tabela_dinamica(visual)

    if tipo == "diagrama":
        return gerar_diagrama(visual)

    return ""


def gerar_grafico_dinamico(visual: dict) -> str:
    dados = visual.get("dados", {})

    x = dados.get("x", [1, 2, 3, 4])
    y = dados.get("y", [1, 4, 9, 16])

    # Utilizando string literal sem quebrar o json do quickchart
    chart = {
        "type": "line",
        "data": {
            "labels": x,
            "datasets": [{"label": "Valor", "data": y}]
        }
    }

    # Substituir aspas duplas por aspas simples ou remover espaços excessivos ajuda nas urls,
    # ou podemos usar urlencode no json dump.
    import json
    chart_json = json.dumps(chart)
    chart_url = "https://quickchart.io/chart?c=" + urllib.parse.quote(chart_json)

    return f"""
<br>
<img src="{chart_url}" />
<br>
"""


def gerar_tabela_dinamica(visual: dict) -> str:
    dados = visual.get("dados", {})
    labels = dados.get("labels", ["Item", "Valor"])
    valores = dados.get("valores", [["Exemplo A", 10], ["Exemplo B", 20]])

    tabela = "\n\n|" + "|".join(labels) + "|\n"
    tabela += "|" + "|".join(["---"] * len(labels)) + "|\n"

    for linha in valores:
        tabela += "|" + "|".join(map(str, linha)) + "|\n"

    return tabela + "\n\n"

def gerar_diagrama(visual: dict) -> str:
    # Fallback simples caso IA peça diagrama. Na v2 podemos renderizar mermaid real
    # se o front aguentar, ou apenas formatar. Por segurança, se não suportar bem:
    return ""
