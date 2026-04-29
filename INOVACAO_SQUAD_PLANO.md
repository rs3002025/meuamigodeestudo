# Conselho de Evolução (10 especialistas) — Amigo de Estudo

## Objetivo
Transformar o sistema em uma plataforma realmente inovadora, profissional e com didática de mentor humano.

## Diagnóstico por especialidade
1. **Head de Produto**: experiência atual resolve fluxo, mas não entrega “efeito uau” de mentoria.
2. **Especialista em Aprendizagem**: conteúdo sem rubric pedagógico automático.
3. **Eng. de IA**: pipeline de geração monolítico; falta etapa de crítica/revisão da própria resposta.
4. **Eng. de Dados**: ausência de métricas de aprendizado por conceito.
5. **UX Writer**: voz do mentor inconsistente.
6. **Designer de Interação**: visual não está embutido ao raciocínio, fica “bloco isolado”.
7. **Eng. Frontend**: falta componente de explicação+gráfico sincronizados.
8. **Eng. Backend**: falta versionamento de prompt e trilha de auditoria.
9. **QA/Quality**: falta suíte de testes de qualidade didática.
10. **Growth/Retention**: falta mecânica de reengajamento orientada por risco de abandono.

## Consenso técnico de evolução (prioridade alta)

### P1 — Didática confiável (2 semanas)
- Pipeline de 2 estágios:
  1) Gerador de aula.
  2) Crítico pedagógico (revisa clareza, precisão e aplicabilidade).
- Gate de qualidade mínimo antes de mostrar aula.

### P2 — Visual como parte do raciocínio (2 a 4 semanas)
- Inserção automática de visuais de apoio no meio da aula para temas matemáticos.
- Componente “passo ↔ gráfico” (destacar trecho do texto e ponto correspondente no gráfico).
- Biblioteca de templates visuais por assunto (funções, estatística, geometria).

### P3 — Personalização profunda (4 a 8 semanas)
- `learning_profile` por usuário (dificuldade ideal, ritmo, erros por conceito).
- Próxima tarefa decidida por domínio real (não só sequência fixa).

### P4 — Inovação percebida (8+ semanas)
- Modo “Mentor Socrático”: perguntas curtas guiando o aluno até resposta.
- “Simulador de prova adaptativo” com feedback metacognitivo.
- “Reexplicar de 3 jeitos”: curto, visual, analogia de cotidiano.

## Entregas já iniciadas neste ciclo
- Inserção automática de gráficos de apoio quando a aula contém função matemática.
- Fallback temático para trigonometria e função quadrática quando a IA não explicita função.
- Ajuste no frontend para apresentar visuais com títulos pedagógicos (não só “Visualizando”).

## Backlog técnico recomendado
1. Criar `services/quality_guard.py`.
2. Criar `services/lesson_reviewer.py` (crítico pedagógico).
3. Persistir `prompt_version` e `quality_score` em `tasks.payload`.
4. Criar endpoint de feedback por bloco (`/api/aula/feedback-bloco`).
5. Criar testes de contrato do JSON de aula.
