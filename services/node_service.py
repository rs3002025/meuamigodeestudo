def gerar_mensagem_diaria(
    taxa_acerto: float = 0.7,
    pendencias: int = 0,
    dias_sem_estudar: int = 0,
    dias_consecutivos: int = 0,
) -> str:
    if dias_sem_estudar >= 1:
        return "tu sumiu ontem 👀 bora voltar hoje sem drama"

    if pendencias > 0:
        if taxa_acerto < 0.6:
            return "tu vacilou nisso, bora corrigir. faz a primeira tarefa agora e resolve"
        return "sem pular etapa. fecha a próxima tarefa agora"

    if taxa_acerto > 0.8 and dias_consecutivos >= 2:
        return "boa, isso aqui fechou. hoje a gente reduz repetição e sobe nível"

    if taxa_acerto > 0.8:
        return "boa, isso aqui fechou. segue pro próximo bloco"

    return "faz isso agora e resolve"


def feedback_conclusao(ordem_tarefa: int, total: int) -> str:
    if ordem_tarefa >= total:
        return "boa, isso aqui fechou"
    return "ok, segue pro próximo"
