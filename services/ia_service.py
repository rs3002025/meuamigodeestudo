from datetime import datetime, timezone


def gerar_questoes(tema: str = "tema geral", quantidade: int = 3) -> list[dict]:
    stamp = int(datetime.now(timezone.utc).timestamp())
    return [
        {
            "id": f"q-{stamp}-{i + 1}",
            "tema": tema,
            "enunciado": f"Questão {i + 1}: explique o conceito principal de {tema} em 3 linhas.",
            "tipo": "aberta",
        }
        for i in range(quantidade)
    ]


def classificar_erro(resposta_correta: str, resposta_usuario: str) -> str:
    if not resposta_usuario or len(resposta_usuario.strip()) < 4:
        return "distracao"

    palavras = [p for p in resposta_correta.lower().split(" ") if len(p) > 4]
    acertou = any(palavra in resposta_usuario.lower() for palavra in palavras)
    return "interpretacao" if acertou else "conteudo"


def gerar_avaliacao_invisivel(objetivo: str | list[str]) -> dict:
    temas = objetivo if isinstance(objetivo, list) else [objetivo]
    return {
        "surpresa": True,
        "questoes": gerar_questoes(temas[0] if temas[0] else "revisão geral", 2),
        "observacao": "Avaliação rápida surpresa para medir retenção real.",
    }
