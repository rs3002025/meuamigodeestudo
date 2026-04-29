# Roadmap de Evolução — Amigo de Estudo

## 1) Diagnóstico objetivo (estado atual)

Com base na leitura do código:
- O produto já possui uma espinha dorsal boa (onboarding → plano → tarefas → revisão), mas a camada didática depende quase totalmente de um único prompt longo sem rubric de qualidade verificável.
- Há fallback funcional, porém com experiência percebida como “erro técnico”, quebrando a sensação de produto premium.
- O motor visual é útil para funções matemáticas, mas ainda frágil em expressões fora do padrão e sem critérios de “quando NÃO mostrar visual”.
- O banco atual privilegia armazenamento operacional, mas ainda não possui uma malha robusta de avaliação de qualidade pedagógica por conteúdo gerado.

## 2) Principais lacunas para virar “mentor de verdade”

### A. Qualidade pedagógica inconsistente
- Falta um rubric automático de clareza, precisão, contexto real e progressão de dificuldade.
- O conteúdo pode soar genérico porque não há “perfil de aprendizagem” persistido por usuário (ritmo, erros recorrentes, estilo preferido).

### B. Personalização limitada
- O sistema registra erros (error_notebook), mas ainda usa pouco esse dado para adaptação didática profunda.

### C. Visualização sem estratégia
- Visual é gerado por bloco, mas sem decisão de utilidade pedagógica (muitas vezes visual “bonito” mas inútil para resolver questão).

### D. Percepção de inovação/profissionalismo
- Sem padrão de voz editorial consistente (mentor confiável + direto).
- Sem telemetria avançada de qualidade percebida por aula (ex: “clareza”, “aplicabilidade”, “confiança”).

## 3) Plano de evolução em 3 ondas

## Onda 1 (0–3 semanas) — Ganho rápido de qualidade percebida
1. **Prompt pedagógico com estrutura fixa de ensino** (já iniciado neste ciclo).
2. **Validador de saída da IA** antes de exibir:
   - Rejeitar respostas sem seções didáticas mínimas.
   - Rejeitar exercícios sem contexto.
3. **Fallback premium**:
   - Em vez de “erro técnico”, entregar mini-aula local segura com 1 exemplo e 1 exercício orientado.
4. **Feedback de 1 clique por aula**:
   - “Claro”, “Mais ou menos”, “Confuso”.

## Onda 2 (3–8 semanas) — Personalização real
1. **Perfil de aprendizagem no banco**:
   - Tabela `learning_profile` com ritmo, lacunas, preferências, histórico de formato eficaz.
2. **Pipeline adaptativo**:
   - Dificuldade inicial de cada tarefa baseada em desempenho real e caderno de erros.
3. **Revisão inteligente**:
   - Reforço espaçado não só por erro, mas por risco de esquecimento + criticidade do tópico.

## Onda 3 (8–16 semanas) — Diferenciação de mercado
1. **Modo Mentor Proativo**:
   - “Você travou aqui 3 vezes; vamos mudar a explicação.”
2. **Trilhas por objetivo real**:
   - ENEM, concurso, faculdade, recolocação profissional.
3. **Laboratório visual confiável**:
   - Renderização determinística para matemática, física e estatística com templates validados.

## 4) Métricas de sucesso (produto e didática)

- **TCR (Task Completion Rate)** por dia/semana.
- **Clareza percebida** (nota 1–5 pós-aula).
- **Tempo até entendimento** (tentativas até acertar exercício intermediário).
- **Retenção D7 / D30**.
- **Taxa de reexplicação** (quando usuário pede “explica de outro jeito”).

## 5) Recomendações técnicas imediatas

1. Criar uma camada `quality_guard.py` para validar JSON didático antes do frontend.
2. Versionar prompts (`prompt_version`) no payload de tarefas para auditoria.
3. Registrar telemetria por bloco (`explicacao_lida`, `visual_expandido`, `exercicio_errado`).
4. Adicionar testes automatizados para:
   - Integridade do JSON de aula.
   - Sanitização de função matemática no visual engine.

## 6) Observação sobre banco remoto informado

Foi tentado acesso ao PostgreSQL remoto fornecido para mapear schema e volumetria, porém o ambiente retornou erro de rede (“Network is unreachable”). Assim, o diagnóstico de banco foi feito a partir do schema local implementado no código (`services/db.py`).
