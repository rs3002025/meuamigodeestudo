def gerar_mensagem_diaria(
    taxa_acerto: float = 0.7,
    pendencias: int = 0,
    dias_sem_estudar: int = 0,
    dias_consecutivos: int = 0,
    materia_do_dia: str | None = None,
) -> str:
    materia = materia_do_dia or "o conteúdo de hoje"

    if dias_sem_estudar >= 1:
        return f"tu sumiu ontem 👀 bora voltar em {materia} sem drama"

    if pendencias > 0:
        if taxa_acerto < 0.6:
            return f"tu vacilou em {materia}, bora corrigir agora."
        return f"bora, hoje é {materia} — só seguir isso aqui"

    if taxa_acerto > 0.8 and dias_consecutivos >= 2:
        return f"boa, {materia} fechou. hoje a gente sobe um pouco o nível"

    if taxa_acerto > 0.8:
        return f"boa, {materia} fechou. segue pro próximo bloco"

    return f"faz {materia} agora e resolve"


def feedback_conclusao(ordem_tarefa: int, total: int) -> str:
    if ordem_tarefa >= total:
        return "boa, isso aqui fechou"
    return "ok, segue pro próximo"
