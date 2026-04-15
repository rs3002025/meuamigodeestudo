FRASES = {
    "motivacao": [
        "Bora, hoje tá leve. Só seguir a sequência e fechar o dia.",
        "Confia no processo: passo a passo e sem inventar moda.",
        "Tu não precisa decidir nada. Só executar o que já tá pronto.",
    ],
    "cobranca": [
        "Tu vacilou nas últimas questões. Vamos reforçar isso agora.",
        "Sem pular etapa. Fecha a tarefa 1 antes de avançar.",
        "Hoje é dia de consistência, não de perfeição.",
    ],
    "reconhecimento": [
        "Isso aqui tu já domina. Vou subir um pouco o nível.",
        "Mandou bem demais no bloco passado. Mantém o ritmo.",
    ],
}


def _pick(lista: list[str], seed: int) -> str:
    return lista[seed % len(lista)]


def gerar_mensagem_diaria(taxa_acerto: float = 0.7, pendencias: int = 0) -> str:
    if pendencias > 0:
        return _pick(FRASES["cobranca"], pendencias)
    if taxa_acerto > 0.82:
        return _pick(FRASES["reconhecimento"], round(taxa_acerto * 100))
    return _pick(FRASES["motivacao"], round(taxa_acerto * 100))
