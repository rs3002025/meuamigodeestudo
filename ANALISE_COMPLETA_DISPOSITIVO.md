# Análise completa do dispositivo (Amigo de Estudo) — versão revisada

## 1) Entendimento do objetivo real do produto

O dispositivo é um **motor de estudo guiado por IA** para reduzir fricção de decisão do aluno. Na prática, ele busca:

- transformar objetivo em plano acionável;
- gerar conteúdo didático com explicação + exemplo + exercícios;
- manter continuidade diária com mensagens curtas e mecânica de sequência;
- registrar progresso para personalizar foco e carga;
- reutilizar conteúdo no banco para reduzir custo no uso recorrente.

Fluxo fim-a-fim identificado:
1. **Onboarding**: captura intenção e recorte de estudo.
2. **Planejamento**: cria trilha com subtemas e ordem de execução.
3. **Geração de tarefas**: materializa a trilha em conteúdo utilizável.
4. **Execução diária**: aluno consome conteúdo e conclui tarefas.
5. **Ajuste adaptativo**: desempenho retroalimenta foco/carga.
6. **Avaliação invisível**: mede retenção sem quebrar experiência.

## 2) Decisões de produto que fazem sentido manter (alinhadas ao momento atual)

### 2.1 Sem limitação de geração no plano free durante implementação/testes
**Manter como está agora é correto**, porque:
- acelera validação de qualidade dos prompts e cobertura curricular;
- permite testes de estresse e tuning de cache sem bloqueios artificiais;
- evita falso negativo de UX em fase de desenvolvimento.

> Observação: essa decisão é de estratégia de estágio do produto, não uma falha técnica neste momento.

### 2.2 Geração da trilha completa em uma única passada
**Também faz sentido manter**, porque:
- conteúdo já gerado é persistido e reutilizado depois;
- melhora disponibilidade futura e reduz dependência de geração síncrona posterior;
- habilita cenário premium de “maratona” (usuário que quer fazer tudo no mesmo dia).

> Portanto, nesta revisão esses dois pontos deixam de ser tratados como problema.

## 3) Falhas e riscos que permanecem relevantes

1. **Inconsistência documentação x execução local (banco)**
   - README cita fallback em memória, porém a camada de dados depende de `DATABASE_URL` para operação real.

2. **Execução com `debug=True` no bootstrap local**
   - Risco de exposição de informações sensíveis se subir em ambiente inadequado.

3. **Validação fraca de entradas numéricas e de payload**
   - Conversões diretas podem gerar erro 500 em input inválido.

4. **Fallback de correção com viés positivo excessivo**
   - Em indisponibilidade da IA, o retorno padrão aprova resposta, enfraquecendo o sinal pedagógico.

5. **Observabilidade limitada**
   - `print` pontual dificulta diagnóstico operacional e análise de incidentes.

6. **Ausência de testes automatizados críticos**
   - Regras de negócio essenciais ainda sem proteção de regressão sistemática.

7. **Processamento matemático sem guard-rails de custo computacional**
   - Entrada complexa pode pressionar CPU em cenários extremos.

## 4) Oportunidades de melhorias funcionais e implementações concretas (aplicar agora)

Abaixo está um pacote único, sem faseamento curto/médio/longo, focado em **funcionalidade real**, diferenciação e ferramentas práticas.

### A) Funcionalidades de aprendizagem (produto)
1. **Diagnóstico inicial adaptativo (mini prova de nivelamento)**
   - Antes da trilha final, aplicar 5–8 questões para ajustar nível automaticamente.

2. **Revisão espaçada automática (SRS)**
   - Gerar tarefas de revisão baseadas em taxa de acerto e tempo desde último contato do tema.

3. **Banco de erros do aluno (Error Notebook)**
   - Guardar erros por tipo, tema e padrão; gerar “missões de correção” personalizadas.

4. **Modo prova real (simulado cronometrado)**
   - Sessões com tempo, peso por questão e relatório final com diagnóstico por competência.

5. **Trilha por meta de data (deadline planner)**
   - Usuário informa data-alvo (ENEM, concurso, prova escolar); sistema reorganiza sequência e intensidade.

6. **Recomendador de próximo passo pós-tarefa**
   - Ao concluir bloco, sugerir automaticamente: reforço, avanço, simulado curto ou revisão.

7. **Resumo inteligente pós-estudo em 60 segundos**
   - Entregar “o que você aprendeu hoje”, “onde errou” e “próxima ação ideal”.

8. **Modo professor/responsável**
   - Painel simplificado com presença, evolução e alertas de risco acadêmico.

### B) Ferramentas de operação e qualidade (engenharia de produto)
9. **Telemetry completa de aprendizado e uso**
   - Eventos: geração, conclusão, acerto, abandono, fallback IA, tempo por tarefa.
   - Ferramentas sugeridas: OpenTelemetry + Grafana/Loki/Tempo.

10. **Feature flags para liberar funcionalidades com segurança**
   - Ferramentas sugeridas: Unleash ou LaunchDarkly.

11. **Pipeline de avaliação de prompts e qualidade de conteúdo**
   - Conjunto fixo de casos e rubricas para comparar versões de prompt/modelo.

12. **Camada anti-regressão pedagógica**
   - Testes automatizados para garantir estrutura mínima de aula e qualidade de exercícios.

13. **Painel de custo por usuário/turma**
   - Medir custo IA por fluxo, por tema e por perfil para decisões comerciais.

14. **Sistema de fila para pré-geração e reprocessamento de conteúdo**
   - Ferramentas sugeridas: Celery/RQ + Redis.
   - Reduz latência de requisição e desacopla geração pesada.

15. **Validação de contrato de payload com schema versionado**
   - Pydantic/JSON Schema para entrada/saída estáveis e melhor evolução de API.

### C) Melhorias de experiência e retenção
16. **Gamificação útil (não superficial)**
   - Streak com valor pedagógico, metas semanais, badges por domínio real de tema.

17. **Notificações inteligentes baseadas em risco de abandono**
   - Disparo por padrão comportamental (queda de acerto, dias sem estudo, abandono recorrente).

18. **Modo foco/offline leve no frontend**
   - Estudo sem distrações e reabertura rápida do último ponto em dispositivos móveis.

19. **Biblioteca pessoal de conteúdo já gerado**
   - Busca por matéria/tema com “favoritos”, histórico e reuso imediato.

20. **Comparativo de evolução por janela temporal**
   - 7/14/30 dias com indicador de domínio por assunto.

## 5) Plano de execução único (sem etapas separadas)

Aplicar em lote com quatro frentes paralelas, desde já:

- **Frente Produto Pedagógico**: itens 1–8 e 16–20.
- **Frente Plataforma e Dados**: itens 9, 13, 14, 15.
- **Frente Qualidade/Confiabilidade**: itens 3, 4, 6, 7, 11, 12.
- **Frente Go-to-Market Técnico**: preparação de modo premium (maratona), analytics e governança de custo.

## 6) Conclusão executiva revisada

O dispositivo está bem posicionado para seguir com estratégia agressiva de implementação: **manter geração ampla sem limite no ambiente atual e manter geração integral da trilha** são decisões compatíveis com o estágio de desenvolvimento e com o plano premium futuro. O ganho agora vem de combinar robustez técnica com funcionalidades de alto valor percebido (diagnóstico adaptativo, revisão espaçada, simulados, painel de evolução, biblioteca de conteúdo e telemetria forte), entregando não só correções, mas avanço real de produto.
